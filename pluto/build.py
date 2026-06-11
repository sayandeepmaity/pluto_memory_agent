"""Merge per-file extractions into a NetworkX DiGraph + JSON round-trip."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import networkx as nx


def build(extractions: list[dict]) -> nx.DiGraph:
    """Merge a list of `{nodes, edges}` extractions into a single DiGraph.

    Missing edge endpoints become `stub` nodes so traversal can still
    follow the edge during query time.
    """
    G = nx.DiGraph()
    for ex in extractions:
        for node in ex.get("nodes", []):
            nid = node["id"]
            attrs = {k: v for k, v in node.items() if k != "id"}
            if G.has_node(nid):
                existing = G.nodes[nid]
                stub = existing.get("type") == "stub"
                for k, v in attrs.items():
                    if stub or k not in existing:
                        existing[k] = v
            else:
                G.add_node(nid, **attrs)
        for edge in ex.get("edges", []):
            s = edge["source"]
            t = edge["target"]
            if not G.has_node(s):
                G.add_node(s, type="stub", name=s, confidence="INFERRED")
            if not G.has_node(t):
                G.add_node(t, type="stub", name=t, confidence="INFERRED")
            data = {k: v for k, v in edge.items() if k not in {"source", "target"}}
            if G.has_edge(s, t):
                existing = G.edges[s, t]
                for k, v in data.items():
                    existing.setdefault(k, v)
            else:
                G.add_edge(s, t, **data)
    return G


def to_dict(G: nx.DiGraph) -> dict:
    """Serialize a DiGraph to a JSON-safe node-link dict."""
    nodes = []
    for nid, attrs in G.nodes(data=True):
        nodes.append({"id": nid, **{k: v for k, v in attrs.items()}})
    links = []
    for s, t, attrs in G.edges(data=True):
        links.append({"source": s, "target": t, **{k: v for k, v in attrs.items()}})
    return {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": nodes,
        "links": links,
    }


def from_dict(data: dict) -> nx.DiGraph:
    """Parse a node-link dict back into a DiGraph."""
    G = nx.DiGraph()
    for n in data.get("nodes", []):
        nid = n["id"]
        G.add_node(nid, **{k: v for k, v in n.items() if k != "id"})
    for e in data.get("links", []):
        s, t = e["source"], e["target"]
        if not G.has_node(s):
            G.add_node(s, type="stub", name=s)
        if not G.has_node(t):
            G.add_node(t, type="stub", name=t)
        G.add_edge(s, t, **{k: v for k, v in e.items() if k not in {"source", "target"}})
    return G


def save(G: nx.DiGraph, path: Path) -> None:
    """Atomically write a DiGraph to `path` as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = to_dict(G)
    fd, tmp_name = tempfile.mkstemp(prefix=".pluto-graph-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load(path: Path) -> nx.DiGraph:
    """Read a DiGraph back from `path`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return from_dict(data)
