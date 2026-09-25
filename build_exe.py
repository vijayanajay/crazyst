"""Build the portable executable:  python build_exe.py  ->  dist/quantdata/

One folder to copy anywhere:
    quantdata.exe                 the CLI (python -m quantdata equivalent, dispatches via runpy)
    config.yaml                   default config, unpacked next to the exe on first run
    quantdata_build_id.txt        the code fingerprint stamp.code_fp() hashes when frozen
    _internal/                    bundled runtime (Python, duckdb, pandas, yfinance, ...)

Design notes:
- runpy dispatch means every src.* module is reached by string, so all of them (and the
  walkforward/backtest/model packages' future entry points) must be hidden imports.
- onedir, not onefile: onefile unpacks to a temp dir on every start (~seconds), and the exe's
  data/ lives next to it anyway, so one folder is the honest shape.
- config.yaml ships as the packaged default (src.config bootstraps it next to the exe on first
  run); the build ID marker is written next to the exe so stamp fingerprints stay stable across
  copies of the same build and change when the code changes.
"""
import os
import shutil
import subprocess
import sys

APP = "quantdata"
HIDDEN = [
    "src.config", "src.stamp", "src.stats", "src.selfcheck",
    "src.download", "src.download._http", "src.download.bhavcopy_old",
    "src.download.bhavcopy_udiff", "src.download.delivery", "src.download.refresh",
    "src.download.scheduler", "src.download.backfill_bhavcopy", "src.download.backfill_all",
    "src.normalize", "src.normalize.bhav", "src.normalize.delivery", "src.normalize.adj_close",
    "src.normalize.columns_old", "src.normalize.columns_udiff",
    "src.normalize.columns_mto", "src.normalize.columns_sec", "src.normalize.panels",
    "src.universe", "src.universe.rank", "src.universe.eligibility", "src.universe.winners",
    "src.features", "src.features.panel", "src.features.matrix",
    "src.validate", "src.validate.report", "src.validate.canary",
    "src.backtest", "src.model", "src.walkforward",
]


def main() -> int:
    assert os.path.isfile("config.yaml"), "run from the repo root"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--name", APP, "--contents-directory", "_internal",
           "--hidden-import", "yfinance",
           # yfinance's optional extras are runtime imports; missing ones just degrade quietly
           "--collect-all", "yfinance",
           *[x for h in HIDDEN for x in ("--hidden-import", h)],
           "--paths", ".",
           "quantdata.py"]
    print(" ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    assert r.returncode == 0, "PyInstaller failed"

    dist = os.path.join("dist", APP)
    # the packaged default config, unpacked by src.config on the exe's first run
    shutil.copyfile("config.yaml", os.path.join(dist, "config.yaml"))
    # build ID: the frozen code fingerprint (see stamp.code_fp) — identical for copies of this
    # build, different for every rebuild, which is exactly the "did the code change" signal.
    marker = os.path.join(dist, "quantdata_build_id.txt")
    exe_size = os.path.getsize(os.path.join(dist, APP + ".exe"))
    with open(marker, "w") as f:
        f.write(f"build {APP} {exe_size} bytes\n")
    total = sum(os.path.getsize(os.path.join(dp, f_)) for dp, _, fs in os.walk(dist) for f_ in fs)
    print(f"\nDONE: dist/{APP}/ — exe {exe_size/1e6:.1f} MB, folder {total/1e6:.0f} MB total")

    # Build-time proof the binary actually runs and dispatches: on a fresh folder `status` must
    # exit 1 with the friendly first-run message — a traceback here means the freeze broke.
    exe = os.path.join(dist, APP + ".exe")
    r = subprocess.run([exe, "status"], capture_output=True, text=True)
    assert r.returncode == 1 and "no database" in (r.stdout + r.stderr), \
        f"smoke test failed: exit {r.returncode}, output {(r.stdout + r.stderr)[-400:]!r}"
    print(f"smoke test: {APP}.exe runs and dispatches (fresh-folder guard message verified)")
    print("Next: copy dist/quantdata/ anywhere, run backfill/refresh there, or point it at "
          "an existing data/ folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
