"""File discovery, classification, and `.plutoignore` / `.gitignore` handling."""

from __future__ import annotations

import fnmatch
from pathlib import Path

HARD_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "pluto-out",
    "dist",
    "build",
    ".tox",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "target",
    ".next",
    ".nuxt",
}

EXTENSION_KIND = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "text",
    ".txt": "text",
    ".toml": "config",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
    ".ini": "config",
    ".cfg": "config",
}


def classify(path: Path) -> str:
    """Return a coarse 'kind' string for a file path based on its extension."""
    return EXTENSION_KIND.get(path.suffix.lower(), "other")


def _read_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


def read_plutoignore(root: Path) -> list[str]:
    """Read patterns from `.plutoignore`, falling back to `.gitignore`."""
    p = root / ".plutoignore"
    if p.exists():
        return _read_lines(p)
    g = root / ".gitignore"
    if g.exists():
        return _read_lines(g)
    return []


def _pattern_matches(rel: str, pattern: str) -> bool:
    """Match a relative POSIX path against a single gitignore-style pattern."""
    pat = pattern.rstrip("/")
    if pat.startswith("/"):
        pat = pat[1:]
        if "/" in pat:
            return fnmatch.fnmatch(rel, pat) or rel.startswith(pat + "/")
        return rel.split("/", 1)[0] == pat or fnmatch.fnmatch(rel.split("/", 1)[0], pat)
    if "/" in pat:
        return fnmatch.fnmatch(rel, pat) or rel.startswith(pat + "/")
    parts = rel.split("/")
    return any(fnmatch.fnmatch(part, pat) for part in parts)


def _is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    """Apply ignore patterns with `!` negation, last-match-wins."""
    ignored = False
    for raw in patterns:
        if raw.startswith("!"):
            if _pattern_matches(rel_posix, raw[1:]):
                ignored = False
        else:
            if _pattern_matches(rel_posix, raw):
                ignored = True
    return ignored


def collect_files(root: Path) -> list[tuple[Path, str]]:
    """Walk `root` and return `(path, kind)` pairs for files we want to extract."""
    root = root.resolve()
    patterns = read_plutoignore(root)
    results: list[tuple[Path, str]] = []

    def _walk(current: Path) -> None:
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except (PermissionError, OSError):
            return
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                if name in HARD_SKIP_DIRS:
                    continue
                if name.startswith("."):
                    # allow .github but skip most dotdirs
                    if name not in {".github"}:
                        continue
                try:
                    rel = entry.relative_to(root).as_posix()
                except ValueError:
                    continue
                if patterns and _is_ignored(rel + "/", patterns):
                    continue
                _walk(entry)
            elif entry.is_file():
                try:
                    rel = entry.relative_to(root).as_posix()
                except ValueError:
                    continue
                if patterns and _is_ignored(rel, patterns):
                    continue
                kind = classify(entry)
                if kind == "other":
                    continue
                results.append((entry, kind))

    _walk(root)
    return results
