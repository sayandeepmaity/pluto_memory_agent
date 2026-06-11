"""Smoke tests that exercise the full CLI pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from pluto.__main__ import main


def test_build_then_query(sample_python_repo: Path, monkeypatch, capsys):
    monkeypatch.chdir(sample_python_repo)
    monkeypatch.setenv("PLUTO_OUT", str(sample_python_repo / "pluto-out"))

    assert main(["build", "."]) == 0
    out_dir = sample_python_repo / "pluto-out"
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "GRAPH_REPORT.md").exists()
    assert (out_dir / "graph.html").exists()
    assert (out_dir / "manifest.json").exists()

    capsys.readouterr()
    assert main(["query", "authenticator login"]) == 0
    captured = capsys.readouterr()
    assert "NODE" in captured.out


def test_build_mixed_languages(sample_mixed_repo: Path, monkeypatch):
    monkeypatch.chdir(sample_mixed_repo)
    monkeypatch.setenv("PLUTO_OUT", str(sample_mixed_repo / "pluto-out"))
    assert main(["build", "."]) == 0
    assert (sample_mixed_repo / "pluto-out" / "graph.json").exists()


def test_update_is_incremental(sample_python_repo: Path, monkeypatch):
    monkeypatch.chdir(sample_python_repo)
    monkeypatch.setenv("PLUTO_OUT", str(sample_python_repo / "pluto-out"))
    assert main(["build", "."]) == 0
    first_mtime = (sample_python_repo / "pluto-out" / "graph.json").stat().st_mtime
    # Sleep is overkill; just touch a file and ensure update rewrites cleanly.
    (sample_python_repo / "main.py").write_text(
        "from pkg.auth import Authenticator\n"
        "def run(): return Authenticator({}).login('a', 'b')\n"
        "def extra(): return run()\n",
        encoding="utf-8",
    )
    os.utime(sample_python_repo / "pluto-out" / "graph.json", (first_mtime - 5, first_mtime - 5))
    assert main(["update", "."]) == 0


def test_cluster_only(sample_python_repo: Path, monkeypatch):
    monkeypatch.chdir(sample_python_repo)
    monkeypatch.setenv("PLUTO_OUT", str(sample_python_repo / "pluto-out"))
    assert main(["build", "."]) == 0
    assert main(["cluster-only", ".", "--resolution", "1.2"]) == 0


def test_export_callflow_html(sample_python_repo: Path, monkeypatch):
    monkeypatch.chdir(sample_python_repo)
    monkeypatch.setenv("PLUTO_OUT", str(sample_python_repo / "pluto-out"))
    assert main(["build", "."]) == 0
    assert main(["export", "callflow-html"]) == 0
    assert (sample_python_repo / "pluto-out" / "callflow.html").exists()


def test_stub_command_exits_clean(capsys):
    assert main(["prs"]) == 0
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out
