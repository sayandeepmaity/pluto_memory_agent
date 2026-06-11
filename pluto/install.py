"""Install / uninstall the `/pluto` skill into Claude Code."""

from __future__ import annotations

import shutil
from pathlib import Path


def _skill_src() -> Path:
    return Path(__file__).resolve().parent / "skill.md"


def _skill_dst(project: bool, root: Path | None = None) -> Path:
    if project:
        base = (root or Path.cwd()).resolve()
        return base / ".claude" / "skills" / "pluto" / "SKILL.md"
    return Path.home() / ".claude" / "skills" / "pluto" / "SKILL.md"


def install(project: bool = False, root: Path | None = None) -> dict:
    """Copy `pluto/skill.md` into the Claude Code skills directory."""
    dst = _skill_dst(project, root)
    src = _skill_src()
    if not src.exists():
        raise FileNotFoundError(f"Missing skill body at {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    replaced = dst.exists()
    shutil.copy2(src, dst)
    out: dict = {"path": str(dst), "replaced": replaced, "scope": "project" if project else "user"}
    if project:
        out["hint"] = "Consider committing .claude/skills/pluto/SKILL.md."
    return out


def uninstall(project: bool = False, purge: bool = False, root: Path | None = None) -> dict:
    """Remove the installed skill and optionally the `pluto-out/` cache."""
    dst = _skill_dst(project, root)
    removed = False
    if dst.exists():
        try:
            dst.unlink()
            removed = True
        except OSError:
            pass
        parent = dst.parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
    purged = False
    if purge:
        base = (root or Path.cwd()).resolve()
        out_dir = base / "pluto-out"
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            purged = True
    return {
        "path": str(dst),
        "removed": removed,
        "purged": purged,
        "scope": "project" if project else "user",
    }
