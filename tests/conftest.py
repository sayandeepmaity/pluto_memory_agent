"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def sample_python_repo(tmp_path: Path) -> Path:
    """A tiny Python project with imports, a class, and a couple of functions."""
    root = tmp_path / "sample-python"
    root.mkdir()
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "auth.py").write_text(
        "import hashlib\n"
        "from .db import lookup_user\n"
        "\n"
        "def hash_password(pw):\n"
        "    return hashlib.sha256(pw.encode()).hexdigest()\n"
        "\n"
        "class Authenticator:\n"
        "    def __init__(self, db):\n"
        "        self.db = db\n"
        "    def login(self, user, pw):\n"
        "        record = lookup_user(self.db, user)\n"
        "        return record and hash_password(pw) == record['hash']\n",
        encoding="utf-8",
    )
    (root / "pkg" / "db.py").write_text(
        "def lookup_user(db, name):\n"
        "    return db.get(name)\n",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "from pkg.auth import Authenticator\n"
        "\n"
        "def run():\n"
        "    a = Authenticator({})\n"
        "    return a.login('x', 'y')\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def sample_mixed_repo(tmp_path: Path) -> Path:
    """A mixed Python + Markdown + JS project for cross-language extraction tests."""
    root = tmp_path / "sample-mixed"
    root.mkdir()
    (root / "service.py").write_text(
        "def handler(req): return req\n",
        encoding="utf-8",
    )
    (root / "client.js").write_text(
        "import { fetch } from 'node-fetch';\n"
        "export function call() { return fetch('/x'); }\n"
        "export class Client { run() { return call(); } }\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Sample\n\n## Overview\n\nSee [docs](docs/index.html).\n",
        encoding="utf-8",
    )
    return root
