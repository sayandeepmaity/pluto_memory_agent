"""Louvain community detection over the (undirected view of the) graph."""

from __future__ import annotations

import networkx as nx

MAX_COMMUNITY_FRACTION = 0.25
DEFAULT_SEED = 42


def cluster(G: nx.DiGraph, resolution: float = 1.0, seed: int = DEFAULT_SEED) -> dict[int, list[str]]:
    """Return `{community_id: [node_ids]}` using Louvain on an undirected view.

    Communities larger than 25% of the graph are split into roughly equal halves
    by re-running Louvain on the induced subgraph with a higher resolution.
    """
    if G.number_of_nodes() == 0:
        return {}
    UG = G.to_undirected(as_view=False)
    try:
        from networkx.algorithms.community import louvain_communities
        communities = louvain_communities(UG, resolution=resolution, seed=seed)
    except Exception:
        communities = list(nx.connected_components(UG))

    out: dict[int, list[str]] = {}
    next_id = 0
    threshold = max(1, int(G.number_of_nodes() * MAX_COMMUNITY_FRACTION))

    def _emit(members: set | list, current_resolution: float, recurse_depth: int) -> None:
        nonlocal next_id
        members = list(members)
        if len(members) <= threshold or recurse_depth >= 3 or len(members) < 4:
            out[next_id] = sorted(members)
            next_id += 1
            return
        sub = UG.subgraph(members)
        try:
            from networkx.algorithms.community import louvain_communities
            split = louvain_communities(sub, resolution=current_resolution * 1.5, seed=seed)
        except Exception:
            out[next_id] = sorted(members)
            next_id += 1
            return
        if len(split) <= 1:
            out[next_id] = sorted(members)
            next_id += 1
            return
        for piece in split:
            _emit(piece, current_resolution * 1.5, recurse_depth + 1)

    for community in communities:
        _emit(community, resolution, 0)

    return out


def attach_communities(G: nx.DiGraph, communities: dict[int, list[str]]) -> None:
    """Write a `community` attribute on every node in `G`."""
    for cid, nodes in communities.items():
        for nid in nodes:
            if G.has_node(nid):
                G.nodes[nid]["community"] = cid
