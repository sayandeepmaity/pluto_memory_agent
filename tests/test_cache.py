from pathlib import Path

from pluto import cache as cache_mod


def test_cache_roundtrip(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("x=1", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    assert cache_mod.load(f, cache_dir) is None
    cache_mod.save(f, cache_dir, {"nodes": [{"id": "a"}], "edges": []})
    out = cache_mod.load(f, cache_dir)
    assert out is not None
    assert out["nodes"][0]["id"] == "a"


def test_cache_invalidates_on_change(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("x=1", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_mod.save(f, cache_dir, {"nodes": [{"id": "a"}], "edges": []})
    f.write_text("x=2", encoding="utf-8")
    assert cache_mod.load(f, cache_dir) is None


def test_clear(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("x=1", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_mod.save(f, cache_dir, {"nodes": [], "edges": []})
    assert cache_mod.clear(cache_dir) >= 1
