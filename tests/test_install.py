from pathlib import Path

from pluto import install as install_mod


def test_install_project_scope(tmp_path: Path, monkeypatch):
    info = install_mod.install(project=True, root=tmp_path)
    dst = Path(info["path"])
    assert dst.exists()
    assert "# /pluto" in dst.read_text(encoding="utf-8")
    assert info["scope"] == "project"
    assert not info["replaced"]


def test_install_overwrites(tmp_path: Path):
    info1 = install_mod.install(project=True, root=tmp_path)
    assert not info1["replaced"]
    info2 = install_mod.install(project=True, root=tmp_path)
    assert info2["replaced"]


def test_uninstall_removes_skill(tmp_path: Path):
    install_mod.install(project=True, root=tmp_path)
    info = install_mod.uninstall(project=True, root=tmp_path)
    assert info["removed"]
    assert not Path(info["path"]).exists()


def test_uninstall_purge(tmp_path: Path):
    install_mod.install(project=True, root=tmp_path)
    (tmp_path / "pluto-out").mkdir()
    (tmp_path / "pluto-out" / "graph.json").write_text("{}", encoding="utf-8")
    info = install_mod.uninstall(project=True, purge=True, root=tmp_path)
    assert info["purged"]
    assert not (tmp_path / "pluto-out").exists()
