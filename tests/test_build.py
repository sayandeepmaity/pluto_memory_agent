from pathlib import Path

from pluto import build as build_mod


def test_build_merges_nodes_and_edges():
    extractions = [
        {
            "nodes": [{"id": "n1", "type": "function", "name": "f"}],
            "edges": [{"source": "n1", "target": "n2", "type": "calls"}],
        },
        {
            "nodes": [{"id": "n2", "type": "function", "name": "g"}],
            "edges": [],
        },
    ]
    G = build_mod.build(extractions)
    assert G.number_of_nodes() == 2
    assert G.has_edge("n1", "n2")
    assert G.nodes["n2"]["name"] == "g"


def test_build_stubs_missing_endpoints():
    extractions = [
        {
            "nodes": [{"id": "n1", "type": "function", "name": "f"}],
            "edges": [{"source": "n1", "target": "missing", "type": "calls"}],
        }
    ]
    G = build_mod.build(extractions)
    assert G.has_node("missing")
    assert G.nodes["missing"]["type"] == "stub"


def test_save_and_load_roundtrip(tmp_path: Path):
    extractions = [
        {
            "nodes": [{"id": "n1", "type": "function", "name": "f"}],
            "edges": [],
        }
    ]
    G = build_mod.build(extractions)
    p = tmp_path / "graph.json"
    build_mod.save(G, p)
    G2 = build_mod.load(p)
    assert G2.number_of_nodes() == 1
    assert G2.nodes["n1"]["name"] == "f"
