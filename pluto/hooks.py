"""Git hook installer for `pluto update` on commit / checkout."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

HOOK_NAMES = ("post-commit", "post-checkout")
MARKER = "# pluto-managed-hook"


def _hooks_dir(root: Path) -> Path:
    return root / ".git" / "hooks"


def _hook_body() -> str:
    interp = sys.executable or "python3"
    return (
        "#!/usr/bin/env bash\n"
        f"{MARKER}\n"
        f'"{interp}" -m pluto update . >/dev/null 2>&1 || true\n'
    )


def _make_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def install_hooks(root: Path | None = None) -> dict:
    """Write post-commit and post-checkout hooks; refuse to clobber user hooks."""
    base = (root or Path.cwd()).resolve()
    hooks_dir = _hooks_dir(base)
    if not hooks_dir.exists():
        raise FileNotFoundError(
            f"{hooks_dir} not found — is this a git repository?"
        )
    results: dict[str, str] = {}
    for name in HOOK_NAMES:
        path = hooks_dir / name
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="replace")
            if MARKER in existing:
                path.write_text(_hook_body(), encoding="utf-8")
                _make_executable(path)
                results[name] = "refreshed"
                continue
            results[name] = (
                f"refused — {path} already exists and is not pluto-managed. "
                f"Add this line to it manually: "
                f'{sys.executable or "python3"} -m pluto update . >/dev/null 2>&1 || true'
            )
            continue
        path.write_text(_hook_body(), encoding="utf-8")
        _make_executable(path)
        results[name] = "installed"
    return {"root": str(base), "hooks": results}


def uninstall_hooks(root: Path | None = None) -> dict:
    """Remove only the hooks we ourselves wrote."""
    base = (root or Path.cwd()).resolve()
    hooks_dir = _hooks_dir(base)
    results: dict[str, str] = {}
    for name in HOOK_NAMES:
        path = hooks_dir / name
        if not path.exists():
            results[name] = "absent"
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            results[name] = "unreadable"
            continue
        if MARKER not in content:
            results[name] = "skipped — not pluto-managed"
            continue
        try:
            path.unlink()
            results[name] = "removed"
        except OSError as e:
            results[name] = f"failed: {e}"
    return {"root": str(base), "hooks": results}


def status(root: Path | None = None) -> dict:
    """Report which hooks exist and whether pluto manages them."""
    base = (root or Path.cwd()).resolve()
    hooks_dir = _hooks_dir(base)
    info: dict[str, dict] = {}
    for name in HOOK_NAMES:
        path = hooks_dir / name
        entry: dict = {"path": str(path), "present": path.exists()}
        if path.exists():
            try:
                entry["pluto_managed"] = MARKER in path.read_text(encoding="utf-8", errors="replace")
                entry["executable"] = bool(path.stat().st_mode & stat.S_IXUSR)
            except OSError:
                entry["pluto_managed"] = False
                entry["executable"] = False
        info[name] = entry
    return {"root": str(base), "hooks": info, "git_repo": (base / ".git").exists()}
