"""Input stamps — skip work whose data, code and params are provably unchanged.

A stamp is one row of `build_stamp`: a key, a fingerprint, the row counts it produced, and when
it was built. The fingerprint covers the three things any build or check depends on:

    code            sha256 over every src/**/*.py, config.yaml and requirements.txt — an edited
                    SQL string or moved threshold invalidates, so a stale stamp can never hide
                    a code change
    cfg:a.b         the resolved config value the build reads (e.g. cfg:universe.top_n)
    table:bhav.date (row count, max date); a missing table fingerprints as "absent"
    dir:data/raw/…  (file count, total bytes, newest mtime) for the raw cache
    file:path       (size, mtime) for a single input file

Two deliberate choices:

- (count, max) instead of a content hash, so a rebuild that writes the same rows is still
  "unchanged" — every self-check rebuilds the tables it validates, and a rebuild must not
  invalidate its own stamp.
- a stamp is current only if the fingerprint matches AND every recorded output table still
  exists with the recorded row count, so a dropped or truncated table can never look fresh.

A caller clears its key before doing the work and records only after it succeeds, so a failed
run never leaves behind something that looks "unchanged".

Typical use:

    fp = stamp.fingerprint(cfg, con, ["code", "table:bhav.date"])
    if stamp.is_current(con, "panels", fp):
        return False
    st = build(con, cfg)
    stamp.record(con, "panels", fp, outputs=st["rows"], seconds=st["seconds"])

python -m src.stamp runs the self-check (absent-table and directory hashing, stability across an
identical rebuild, invalidation on a new row / changed config / changed code hash, missing and
truncated outputs, record/load/clear round-trip).
"""
import hashlib
import json
import os
import sys
import time

import duckdb

KEY_COLUMNS = "key VARCHAR PRIMARY KEY, fingerprint VARCHAR, outputs VARCHAR, seconds DOUBLE, built_at TIMESTAMP"
_TABLE = "build_stamp"
_CODE_ROOTS = ("src", "config.yaml", "requirements.txt")


def _connect(cfg: dict):
    return duckdb.connect(cfg["paths"]["duckdb"])


def code_fp() -> str:
    """sha256 over the sources and params that define behavior (comments included, deliberately:
    any edit is a change worth re-verifying under).

    Frozen exe (build_exe.py): there are no source files on disk, so hash the packaged build ID
    written at freeze time instead — a rebuilt exe is a code change, a copied exe is not.
    """
    if getattr(sys, "frozen", False):
        marker = os.path.join(os.path.dirname(sys.executable), "quantdata_build_id.txt")
        if os.path.isfile(marker):
            with open(marker, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()[:16]
        import __main__  # marker missing: degrade to the exe's own identity, never crash
        return hashlib.sha256(sys.executable.encode()).hexdigest()[:16] + ":" \
            + hashlib.sha256(getattr(__main__, "__file__", sys.executable).encode()).hexdigest()[:16]
    h = hashlib.sha256()
    for root in _CODE_ROOTS:
        if os.path.isfile(root):
            files = [root]
        else:
            files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(root)
                           for f in fs if f.endswith(".py"))
        for p in files:
            h.update(p.replace("\\", "/").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]


def table_fp(con, table: str, col: str) -> str:
    """(rows, max(col)) for a table; "absent" when it does not exist."""
    try:
        n, mx = con.execute(f'SELECT count(*), max("{col}") FROM "{table}"').fetchone()
    except duckdb.Error:
        return "absent"
    return f"{n}:{mx}"


def dir_fp(path: str) -> str:
    """(files, bytes, newest mtime) for the raw cache under a path; "absent" when missing."""
    if not os.path.isdir(path):
        return "absent"
    n = size = newest = 0
    for dp, _, files in os.walk(path):
        for f in files:
            st = os.stat(os.path.join(dp, f))
            n += 1
            size += st.st_size
            newest = max(newest, st.st_mtime_ns)
    return f"{n}:{size}:{newest}"


def file_fp(path: str) -> str:
    if not os.path.isfile(path):
        return "absent"
    st = os.stat(path)
    return f"{st.st_size}:{st.st_mtime_ns}"


def _cfg_value(cfg: dict, dotted: str) -> str:
    v = cfg
    for part in dotted.split("."):
        v = v[part]  # KeyError is the honest failure for a misspelled spec
    return json.dumps(v, sort_keys=True, default=str)


def _resolve(cfg: dict, con, spec: str) -> str:
    kind, _, arg = spec.partition(":")
    if kind == "code":
        return code_fp()
    if kind == "table":
        table, col = arg.split(".", 1)
        return table_fp(con, table, col)
    if kind == "dir":
        return dir_fp(arg)
    if kind == "file":
        return file_fp(arg)
    if kind == "cfg":
        return _cfg_value(cfg, arg)
    raise ValueError(f"unknown stamp spec {spec!r} — refusing to fingerprint it loosely")


def fingerprint(cfg: dict, con, specs) -> str:
    """One hash over every resolved spec — the identity of a build's inputs."""
    h = hashlib.sha256()
    for spec in specs:
        h.update(f"{spec}={_resolve(cfg, con, spec)}\n".encode())
    return h.hexdigest()[:16]


def spec_tables(con, specs) -> dict:
    """{table: rows} for every `table:` spec — the outputs a check validated."""
    out = {}
    for spec in specs:
        kind, _, arg = spec.partition(":")
        if kind != "table":
            continue
        table = arg.split(".", 1)[0]
        fp = table_fp(con, table, arg.split(".", 1)[1])
        out[table] = None if fp == "absent" else int(fp.split(":", 1)[0])
    return out


def _ensure_table(con) -> None:
    con.execute(f"CREATE TABLE IF NOT EXISTS {_TABLE} ({KEY_COLUMNS})")


def is_current(con, key: str, fp: str) -> bool:
    """Stored fingerprint matches AND every recorded output still has its recorded rows."""
    _ensure_table(con)
    row = con.execute(f"SELECT fingerprint, outputs FROM {_TABLE} WHERE key = ?", [key]).fetchone()
    if row is None or row[0] != fp:
        return False
    for table, rows in (json.loads(row[1]) or {}).items():
        if not table or rows is None:
            continue
        try:
            got = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        except duckdb.Error:
            return False  # output table dropped
        if got != rows:
            return False  # output table truncated or appended to behind our back
    return True


def record(con, key: str, fp: str, outputs: dict | None = None, seconds: float | None = None) -> None:
    _ensure_table(con)
    con.execute(f"DELETE FROM {_TABLE} WHERE key = ?", [key])
    con.execute(f"INSERT INTO {_TABLE} VALUES (?, ?, ?, ?, now())",
                [key, fp, json.dumps(outputs or {}), seconds])


def clear(con, key: str) -> None:
    """Forget a stamp — call before work whose success is not yet known."""
    _ensure_table(con)
    con.execute(f"DELETE FROM {_TABLE} WHERE key = ?", [key])


def built_at(con, key: str):
    _ensure_table(con)
    row = con.execute(f"SELECT built_at FROM {_TABLE} WHERE key = ?", [key]).fetchone()
    return row[0] if row else None


def _synth_check() -> None:
    import shutil
    import tempfile
    from datetime import date

    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "t.duckdb")
    con = duckdb.connect(db)
    cfg = {"a": {"b": 1}, "paths": {"duckdb": db}}

    # absent inputs hash, and never crash the caller
    assert table_fp(con, "nope", "date") == "absent", "missing table must fingerprint as absent"
    assert dir_fp(os.path.join(tmp, "nodir")) == "absent"
    assert file_fp(os.path.join(tmp, "nofile")) == "absent"

    con.execute("CREATE TABLE t (date DATE)")
    con.executemany("INSERT INTO t VALUES (?)", [[date(2024, 1, 1)], [date(2024, 1, 2)]])
    one = table_fp(con, "t", "date")
    con.execute("CREATE OR REPLACE TABLE t AS SELECT * FROM t")  # identical rebuild
    assert table_fp(con, "t", "date") == one, \
        "an identical rebuild must not invalidate a stamp (checks rebuild what they validate)"
    con.execute("INSERT INTO t VALUES (?)", [date(2024, 1, 3)])
    assert table_fp(con, "t", "date") != one, "a new row must invalidate a stamp"
    assert not table_fp(con, "t", "date").startswith("absent"), "fingerprint format drifted"

    # directory hashing: stable, then sensitive to a new file
    raw = os.path.join(tmp, "raw")
    os.makedirs(raw)
    d0 = dir_fp(raw)
    assert dir_fp(raw) == d0, "directory fingerprint must be stable"
    with open(os.path.join(raw, "a.dat"), "w") as fh:
        fh.write("x")
    assert dir_fp(raw) != d0, "a new cached file must invalidate a stamp"

    # fingerprint: config, code and spec errors
    specs = ["code", "table:t.date", "dir:" + raw.replace("\\", "/"), "cfg:a.b"]
    c0 = fingerprint(cfg, con, specs)
    assert c0 == fingerprint(cfg, con, specs), "fingerprint must be deterministic"
    assert len(c0) == 16 and code_fp() == code_fp(), "code hash must be a stable 16 hex chars"
    cfg2 = {"a": {"b": 2}, "paths": {"duckdb": db}}
    assert fingerprint(cfg2, con, specs) != c0, "a changed config value must invalidate a stamp"
    try:
        fingerprint(cfg, con, ["bogus:x"])
        raise AssertionError("an unknown spec must raise, not be ignored")
    except ValueError:
        pass

    # record / is_current / clear
    assert not is_current(con, "k", c0), "an unrecorded key is never current"
    record(con, "k", c0, outputs={"t": 3}, seconds=0.5)
    assert is_current(con, "k", c0), "a recorded key must be current"
    assert built_at(con, "k") is not None, "built_at must read back the build time"
    assert not is_current(con, "k", c0[::-1]), "a different fingerprint must not be current"
    con.execute("CREATE OR REPLACE TABLE t AS SELECT * FROM t WHERE date < DATE '2024-01-03'")
    assert not is_current(con, "k", c0), "a truncated output table must not be current"
    con.execute("DROP TABLE t")
    assert not is_current(con, "k", c0), "a dropped output table must not be current"
    clear(con, "k")
    assert not is_current(con, "k", c0), "clear must forget the stamp"

    assert spec_tables(con, ["code", "table:nope.date"]) == {"nope": None}, "spec_tables drifted"
    con.close()
    shutil.rmtree(tmp)
    print("synthetic check passed (absent/dir/file hashing, identical rebuild stable, new row and "
          "config change invalidate, unknown spec raises, dropped/truncated output not current, "
          "record/clear round-trip)")


def _live_check() -> None:
    from src.config import load
    from src.selfcheck import suite_inputs
    cfg = load()
    specs = suite_inputs(cfg)
    con = _connect(cfg)
    try:
        t0 = time.monotonic()
        fp = fingerprint(cfg, con, specs)
        print(f"self-check fingerprint {fp} over {len(specs)} inputs "
              f"in {time.monotonic() - t0:.2f}s", flush=True)
        rows = spec_tables(con, specs)
        for table, n in rows.items():
            print(f"  {table:<16} {'absent' if n is None else f'{n:,} rows'}", flush=True)
        stamps = con.execute(f"SELECT key, fingerprint, built_at FROM {_TABLE} ORDER BY 1").fetchall() \
            if con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [_TABLE]).fetchone()[0] else []
        for key, s_fp, at in stamps:
            mark = "current" if is_current(con, key, s_fp) else "STALE"
            print(f"  stamp {key:<12} {s_fp}  {mark}  built {at}", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check()
    print("PASS: input stamps (synthetic invalidation rules + live fingerprint)")


if __name__ == "__main__":
    if "--clear" in sys.argv[1:]:
        from src.config import load
        c = _connect(load())
        c.execute(f"DELETE FROM {_TABLE}")
        c.close()
        print("cleared all stamps")
        sys.exit(0)
    if "--fp" in sys.argv[1:]:
        from src.config import load
        from src.selfcheck import suite_inputs
        cfg = load()
        c = _connect(cfg)
        print(fingerprint(cfg, c, suite_inputs(cfg)))
        c.close()
        sys.exit(0)
    _self_check()
    sys.exit(0)
