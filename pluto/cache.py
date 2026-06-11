"""Per-file extraction cache, keyed by SHA-256 of the file contents.

Cache directory lives at `<output_dir>/cache/`. Writes are atomic
(tempfile + `os.replace`) so a crash mid-write can't corrupt the cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


def _digest(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _cache_path(cache_dir: Path, sha: str) -> Path:
    return cache_dir / f"{sha}.json"


def load(path: Path, cache_dir: Path) -> dict | None:
    """Return the cached extraction for `path` if the file is unchanged."""
    sha = _digest(path)
    if sha is None:
        return None
    cp = _cache_path(cache_dir, sha)
    if not cp.exists():
        return None
    try:
        return json.loads(cp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save(path: Path, cache_dir: Path, result: dict) -> None:
    """Persist `result` to the cache keyed by the SHA-256 of `path`."""
    sha = _digest(path)
    if sha is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(cache_dir, sha)
    fd, tmp_name = tempfile.mkstemp(prefix=".pluto-cache-", dir=str(cache_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp_name, cp)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def clear(cache_dir: Path) -> int:
    """Remove every cache entry. Returns the count of files removed."""
    if not cache_dir.exists():
        return 0
    count = 0
    for entry in cache_dir.iterdir():
        if entry.is_file() and entry.suffix == ".json":
            try:
                entry.unlink()
                count += 1
            except OSError:
                continue
    return count
