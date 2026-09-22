"""Shared HTTP discipline for all downloaders (plan working rule 4: cache, never re-fetch).

One `fetch` used by every source module:
- browser-like headers (NSE bot-blocks plain clients; bare HEAD gets 403 — verified live)
- atomic writes (.part + rename): a killed run never leaves a truncated cache entry
- zip sanity check before caching (starts with PK\x03\x04 and is big enough to be real)
  — `kind="text"` for plain CSV/DAT sources (delivery MTO / sec_bhavdata_full): big enough + not an HTML error page
- retry with linear backoff from config; raises after retries are exhausted — missing data is loud
- sleep between hits (plan task 1.1: "sleep between hits"), even across cache hits

404 is returned as "holiday" by callers that iterate calendars; `fetch` itself never retries it.
404s are also remembered in a negative cache (cfg.paths.raw_404_cache) so reruns over a
filled cache don't re-probe NSE for known holidays. Entries expire after NEG_TTL_DAYS so a
transient server-side 404 of a real trading day can't be baked in forever — the day gets
re-probed monthly, and the 1.7 gap report remains the safety net for silent holes.
"""
import os
import time

import requests

NEG_TTL_DAYS = 30
_NEG_MEMO: dict[str, dict] = {}  # path -> parsed cache; avoids re-reading the file per fetch call


def _load_404(path: str) -> dict:
    if path in _NEG_MEMO:
        return _NEG_MEMO[path]
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path) as f:
        for line in f:
            url, _, ts = line.rstrip("\n").rpartition("\t")
            if url:
                try:
                    out[url] = float(ts)
                except ValueError:
                    continue  # tolerate a corrupt line; it just re-probes
    _NEG_MEMO[path] = out
    return out


def _remember_404(path: str, url: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"{url}\t{time.time()}\n")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports",
}


def _validate(content: bytes, kind: str) -> bool:
    """Cheap content sanity check before anything touches the cache."""
    if kind == "zip":
        return content.startswith(b"PK\x03\x04") and len(content) >= 10_000
    if kind == "text":
        # NSE serves an HTML error page (<!DOCTYPE...> on 404-ish routes); real data is plain CSV/DAT
        return len(content) >= 1_000 and not content[:64].lstrip().startswith((b"<!DOCTYPE", b"<html"))
    raise ValueError(f"unknown kind {kind!r}")


def fetch(session: requests.Session, url: str, out_path: str, cfg: dict, kind: str = "zip") -> str:
    """Download url to out_path unless cached. Returns 'cached' | 'downloaded' | 'holiday'.

    Raises IOError on persistent non-404 failure — callers must not swallow it.
    """
    if os.path.exists(out_path):
        return "cached"

    neg_path = cfg["paths"]["raw_404_cache"]
    first_seen = _load_404(neg_path).get(url)
    if first_seen and time.time() - first_seen < NEG_TTL_DAYS * 86400:
        return "holiday"  # known 404, not older than the TTL

    attempts = cfg["download"]["retry_attempts"]
    sleep_s = cfg["download"]["sleep_seconds"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    part = out_path + ".part"
    for attempt in range(1, attempts + 1):
        try:
            time.sleep(sleep_s)  # be polite on every hit, including the last
            r = session.get(url, headers=HEADERS, timeout=(10, 60))
            if r.status_code == 404:
                _remember_404(neg_path, url)
                return "holiday"
            r.raise_for_status()
            if not _validate(r.content, kind):
                raise IOError(f"content failed {kind} validation ({len(r.content)} bytes) — error page?")
            with open(part, "wb") as f:
                f.write(r.content)
            os.replace(part, out_path)  # atomic
            return "downloaded"
        except Exception as e:
            if attempt == attempts:
                raise IOError(f"{url}: giving up after {attempts} attempts: {e}") from e
            time.sleep(sleep_s * attempt)
    raise AssertionError("unreachable")
