from pathlib import Path

import pytest

from pluto import hooks


def _init_fake_git_repo(root: Path) -> None:
    (root / ".git" / "hooks").mkdir(parents=True)


def test_install_hooks_creates_files(tmp_path: Path):
    _init_fake_git_repo(tmp_path)
    info = hooks.install_hooks(root=tmp_path)
    assert info["hooks"]["post-commit"] == "installed"
    assert info["hooks"]["post-checkout"] == "installed"
    assert (tmp_path / ".git" / "hooks" / "post-commit").exists()


def test_install_hooks_refuses_existing_user_hook(tmp_path: Path):
    _init_fake_git_repo(tmp_path)
    existing = tmp_path / ".git" / "hooks" / "post-commit"
    existing.write_text("#!/bin/sh\necho user hook\n", encoding="utf-8")
    info = hooks.install_hooks(root=tmp_path)
    assert "refused" in info["hooks"]["post-commit"]


def test_install_hooks_refreshes_pluto_managed_hook(tmp_path: Path):
    _init_fake_git_repo(tmp_path)
    hooks.install_hooks(root=tmp_path)
    info = hooks.install_hooks(root=tmp_path)
    assert info["hooks"]["post-commit"] == "refreshed"


def test_uninstall_only_removes_pluto_managed(tmp_path: Path):
    _init_fake_git_repo(tmp_path)
    existing = tmp_path / ".git" / "hooks" / "post-commit"
    existing.write_text("#!/bin/sh\necho user\n", encoding="utf-8")
    info = hooks.uninstall_hooks(root=tmp_path)
    assert "skipped" in info["hooks"]["post-commit"]
    assert existing.exists()


def test_status_reports_layout(tmp_path: Path):
    _init_fake_git_repo(tmp_path)
    hooks.install_hooks(root=tmp_path)
    info = hooks.status(root=tmp_path)
    assert info["git_repo"]
    assert info["hooks"]["post-commit"]["present"]
    assert info["hooks"]["post-commit"]["pluto_managed"]


def test_install_hooks_errors_without_git(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        hooks.install_hooks(root=tmp_path)
