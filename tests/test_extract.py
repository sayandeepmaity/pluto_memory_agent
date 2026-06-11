from pathlib import Path

from pluto.extract import extract


def test_python_function_and_class(tmp_path: Path):
    src = tmp_path / "m.py"
    src.write_text(
        "import os\n"
        "def f(): pass\n"
        "class C:\n"
        "    def m(self): return f()\n",
        encoding="utf-8",
    )
    out = extract(src, tmp_path)
    kinds = {n["type"] for n in out["nodes"]}
    assert {"file", "module", "function", "class"}.issubset(kinds)
    names = {n["name"] for n in out["nodes"]}
    assert "f" in names
    assert "C" in names


def test_python_calls_are_inferred(tmp_path: Path):
    src = tmp_path / "m.py"
    src.write_text(
        "def a(): return b()\n"
        "def b(): return 1\n",
        encoding="utf-8",
    )
    out = extract(src, tmp_path)
    calls = [e for e in out["edges"] if e["type"] == "calls"]
    assert calls
    assert all(c["confidence"] == "INFERRED" for c in calls)


def test_javascript_imports_and_functions(tmp_path: Path):
    src = tmp_path / "x.js"
    src.write_text(
        "import { foo } from 'bar';\n"
        "export function hello() { return foo(); }\n"
        "export class A {}\n",
        encoding="utf-8",
    )
    out = extract(src, tmp_path)
    types = {n["type"] for n in out["nodes"]}
    assert "module" in types
    assert "function" in types
    assert "class" in types


def test_go_extraction(tmp_path: Path):
    src = tmp_path / "x.go"
    src.write_text(
        'package main\n'
        'import (\n  "fmt"\n  "os"\n)\n'
        'func Hello() {}\n'
        'type Foo struct {}\n',
        encoding="utf-8",
    )
    out = extract(src, tmp_path)
    names = {n["name"] for n in out["nodes"]}
    assert "Hello" in names
    assert "Foo" in names
    assert "fmt" in names


def test_markdown_headings_and_links(tmp_path: Path):
    src = tmp_path / "README.md"
    src.write_text("# Title\n\n## Section\n\n[link](page.html)\n", encoding="utf-8")
    out = extract(src, tmp_path)
    types = [n["type"] for n in out["nodes"]]
    assert "heading" in types
    assert "link" in types


def test_unknown_extension_returns_file_node(tmp_path: Path):
    src = tmp_path / "x.txt"
    src.write_text("hello", encoding="utf-8")
    out = extract(src, tmp_path)
    assert len(out["nodes"]) == 1
    assert out["nodes"][0]["type"] == "file"
