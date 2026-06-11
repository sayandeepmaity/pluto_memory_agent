from pathlib import Path

from pluto.detect import classify, collect_files, read_plutoignore


def test_classify_python():
    assert classify(Path("foo.py")) == "python"
    assert classify(Path("foo.md")) == "markdown"
    assert classify(Path("foo.go")) == "go"
    assert classify(Path("foo.unknown")) == "other"


def test_collect_files_skips_hard_dirs(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x=1", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("", encoding="utf-8")

    files = collect_files(tmp_path)
    rels = {p.name for p, _ in files}
    assert "a.py" in rels
    assert "config" not in rels
    assert "lib.js" not in rels


def test_collect_files_respects_plutoignore(tmp_path: Path):
    (tmp_path / "keep.py").write_text("x=1", encoding="utf-8")
    (tmp_path / "skip.py").write_text("x=1", encoding="utf-8")
    (tmp_path / ".plutoignore").write_text("skip.py\n", encoding="utf-8")

    files = collect_files(tmp_path)
    names = {p.name for p, _ in files}
    assert "keep.py" in names
    assert "skip.py" not in names


def test_plutoignore_negation(tmp_path: Path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    (tmp_path / ".plutoignore").write_text("*.py\n!a.py\n", encoding="utf-8")
    files = collect_files(tmp_path)
    names = {p.name for p, _ in files}
    assert "a.py" in names
    assert "b.py" not in names


def test_plutoignore_falls_back_to_gitignore(tmp_path: Path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("b.py\n", encoding="utf-8")
    patterns = read_plutoignore(tmp_path)
    assert "b.py" in patterns
