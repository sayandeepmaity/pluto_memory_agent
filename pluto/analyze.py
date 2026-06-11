"""God-node detection, cross-community surprises, and suggested questions."""

from __future__ import annotations

import networkx as nx

BUILTIN_NOISE = {
    "module::os", "module::sys", "module::re", "module::json", "module::pathlib",
    "module::typing", "module::collections", "module::dataclasses", "module::abc",
    "module::functools", "module::itertools", "module::logging",
}


def god_nodes(G: nx.DiGraph, top_n: int = 20) -> list[dict]:
    """Top-N nodes by total degree, with a small builtin-noise filter."""
    rows: list[tuple[int, str, dict]] = []
    for nid, deg in G.degree():
        if nid in BUILTIN_NOISE:
            continue
        rows.append((deg, nid, G.nodes[nid]))
    rows.sort(key=lambda r: (-r[0], r[1]))
    out: list[dict] = []
    for deg, nid, attrs in rows[:top_n]:
        out.append({
            "id": nid,
            "degree": deg,
            "type": attrs.get("type", "?"),
            "name": attrs.get("name", nid),
            "src": attrs.get("src"),
            "community": attrs.get("community"),
        })
    return out


def surprises(G: nx.DiGraph, communities: dict[int, list[str]], top_n: int = 10) -> list[dict]:
    """Cross-community edges between high-degree nodes — likely architectural seams."""
    if not communities:
        return []
    node_to_comm: dict[str, int] = {}
    for cid, members in communities.items():
        for nid in members:
            node_to_comm[nid] = cid
    deg = dict(G.degree())
    candidates: list[tuple[int, str, str, dict]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for s, t, attrs in G.edges(data=True):
        cs, ct = node_to_comm.get(s), node_to_comm.get(t)
        if cs is None or ct is None or cs == ct:
            continue
        key = (s, t) if s < t else (t, s)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        score = deg.get(s, 0) + deg.get(t, 0)
        candidates.append((score, s, t, attrs))
    candidates.sort(key=lambda r: -r[0])
    out: list[dict] = []
    for score, s, t, attrs in candidates[:top_n]:
        out.append({
            "score": score,
            "source": s,
            "target": t,
            "source_community": node_to_comm.get(s),
            "target_community": node_to_comm.get(t),
            "type": attrs.get("type", "edge"),
            "src": attrs.get("src"),
        })
    return out


def suggest_questions(G: nx.DiGraph, communities: dict[int, list[str]] | None = None) -> list[str]:
    """A few seeded natural-language questions to bootstrap a query session."""
    suggestions: list[str] = []
    gods = god_nodes(G, top_n=5)
    for g in gods[:3]:
        name = g["name"]
        kind = g["type"]
        if kind == "function":
            suggestions.append(f"How does the `{name}` function work?")
        elif kind == "class":
            suggestions.append(f"What does the `{name}` class do?")
        elif kind == "module":
            suggestions.append(f"What relies on the `{name}` module?")
        elif kind == "file":
            suggestions.append(f"Walk me through `{name}`.")
        else:
            suggestions.append(f"What is `{name}`?")
    if communities and len(communities) > 1:
        suggestions.append("How are the major subsystems connected?")
    suggestions.append("What's the architectural entry point of this project?")
    return suggestions[:6]
