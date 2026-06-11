from pathlib import Path

from pluto import build as build_mod
from pluto import cache as cache_mod
from pluto import detect, extract, query


def _build_graph(root: Path):
    extractions = []
    for path, _ in detect.collect_files(root):
        extractions.append(extract.extract(path, root))
    return build_mod.build(extractions)


def test_query_returns_subgraph(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    out = query.answer(G, "how does authentication work", depth=2, budget=2000)
    assert "NODE" in out
    assert "Authenticator" in out or "authenticator" in out.lower()


def test_query_budget_is_respected(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    out = query.answer(G, "auth login user", depth=4, budget=50)
    # 50 tokens × 4 chars/token = 200 chars of output max.
    assert len(out.split("NODE")) <= 6


def test_query_no_match_suggests_god_nodes(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    out = query.answer(G, "xyzzy_nonexistent_term", depth=2, budget=2000)
    assert "No matching nodes" in out
    assert "Did you mean" in out


def test_explain_known_node(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    target = next(
        nid for nid, attrs in G.nodes(data=True)
        if attrs.get("name") == "Authenticator"
    )
    out = query.explain(G, target)
    assert "NODE" in out


def test_path_between_nodes(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    out = query.path(G, "Authenticator", "lookup_user")
    assert "PATH" in out or "No path" in out


def test_affected_traversal(sample_python_repo: Path):
    G = _build_graph(sample_python_repo)
    out = query.affected(G, "Authenticator", depth=2)
    assert "AFFECTED" in out or "Unknown" in out
