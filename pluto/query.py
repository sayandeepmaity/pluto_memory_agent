"""Token-budgeted graph queries.

The whole point of pluto: at query time we read `graph.json` and emit a
compact subgraph, never the original corpus.
"""

from __future__ import annotations

import re
from collections import deque

import networkx as nx

CHARS_PER_TOKEN = 4
_TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "could", "may", "might", "must", "shall", "can",
    "of", "in", "on", "at", "to", "for", "with", "from", "by", "as", "if",
    "this", "that", "these", "those", "it", "its", "i", "you", "we", "they",
    "what", "which", "who", "how", "why", "when", "where", "does", "do",
    "about", "into", "through", "over", "out", "up", "down", "off", "than",
    "then", "so", "very", "just", "use", "uses", "used", "using",
}


def _terms(question: str) -> list[str]:
    """Tokenize the question into lowercased identifier-like terms."""
    raw = _TERM_RE.findall(question)
    out: list[str] = []
    seen: set[str] = set()
    for t in raw:
        lt = t.lower()
        if lt in STOPWORDS or len(lt) < 2:
            continue
        if lt in seen:
            continue
        seen.add(lt)
        out.append(lt)
    return out


def _prefix_overlap(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _score(node_id: str, attrs: dict, terms: list[str]) -> int:
    """How well a node matches the search terms (case-insensitive)."""
    if not terms:
        return 0
    name = str(attrs.get("name", node_id)).lower()
    short_name = name.rsplit(".", 1)[-1].rsplit("::", 1)[-1]
    nid = node_id.lower()
    score = 0
    matched = False
    for t in terms:
        if t == name or t == short_name:
            score += 10
            matched = True
            continue
        if t in name:
            score += 5
            matched = True
            continue
        if t in nid:
            score += 2
            matched = True
            continue
        overlap = max(_prefix_overlap(t, short_name), _prefix_overlap(t, name))
        if overlap >= 4 and overlap >= min(len(t), len(short_name)) // 2:
            score += 3
            matched = True
    if matched and attrs.get("type") in {"function", "class", "module"}:
        score += 1
    return score


def _seeds(G: nx.DiGraph, terms: list[str], k: int = 8) -> list[str]:
    """Pick the top-k matching nodes for `terms`."""
    scored: list[tuple[int, str]] = []
    for nid, attrs in G.nodes(data=True):
        s = _score(nid, attrs, terms)
        if s > 0:
            scored.append((s, nid))
    scored.sort(key=lambda p: (-p[0], p[1]))
    return [nid for _, nid in scored[:k]]


def _bfs(G: nx.DiGraph, seeds: list[str], depth: int) -> list[str]:
    """Breadth-first expansion from each seed, treating the graph as undirected."""
    visited: set[str] = set()
    order: list[str] = []
    q: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
    while q:
        node, d = q.popleft()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        if d >= depth:
            continue
        neigh = set()
        if G.has_node(node):
            neigh.update(G.successors(node))
            neigh.update(G.predecessors(node))
        for n in neigh:
            if n not in visited:
                q.append((n, d + 1))
    return order


def _dfs(G: nx.DiGraph, seeds: list[str], depth: int) -> list[str]:
    visited: set[str] = set()
    order: list[str] = []

    def _walk(node: str, d: int) -> None:
        if node in visited or d > depth:
            return
        visited.add(node)
        order.append(node)
        if not G.has_node(node):
            return
        for n in list(G.successors(node)) + list(G.predecessors(node)):
            if n not in visited:
                _walk(n, d + 1)

    for s in seeds:
        _walk(s, 0)
    return order


def _node_line(G: nx.DiGraph, nid: str) -> str:
    attrs = G.nodes[nid] if G.has_node(nid) else {}
    kind = attrs.get("type", "?")
    name = attrs.get("name", nid)
    src = attrs.get("src", "?")
    line = attrs.get("line")
    conf = attrs.get("confidence", "?")
    suffix = f":{line}" if line else ""
    return f"NODE id={nid} type={kind} name={name} src={src}{suffix} confidence={conf}"


def _edge_line(G: nx.DiGraph, s: str, t: str) -> str:
    attrs = G.edges[s, t] if G.has_edge(s, t) else {}
    et = attrs.get("type", "edge")
    conf = attrs.get("confidence", "?")
    src = attrs.get("src", "?")
    line = attrs.get("line")
    suffix = f":{line}" if line else ""
    return f"EDGE {s} --[{et}]--> {t} src={src}{suffix} confidence={conf}"


def _render(G: nx.DiGraph, order: list[str], budget: int) -> str:
    """Print NODE lines and the edges they induce, capped at `budget` tokens."""
    if not order:
        return ""
    cap_chars = budget * CHARS_PER_TOKEN
    lines: list[str] = []
    used = 0
    in_set: set[str] = set(order)
    rendered_nodes: set[str] = set()
    rendered_edges: set[tuple[str, str]] = set()

    def _emit(line: str) -> bool:
        nonlocal used
        cost = len(line) + 1
        if used + cost > cap_chars:
            return False
        lines.append(line)
        used += cost
        return True

    for nid in order:
        line = _node_line(G, nid)
        if not _emit(line):
            break
        rendered_nodes.add(nid)
        if G.has_node(nid):
            for tgt in G.successors(nid):
                if tgt in in_set and (nid, tgt) not in rendered_edges:
                    if not _emit(_edge_line(G, nid, tgt)):
                        break
                    rendered_edges.add((nid, tgt))
            for src in G.predecessors(nid):
                if src in in_set and (src, nid) not in rendered_edges and src in rendered_nodes:
                    if not _emit(_edge_line(G, src, nid)):
                        break
                    rendered_edges.add((src, nid))
    return "\n".join(lines)


def _god_nodes(G: nx.DiGraph, k: int = 5) -> list[str]:
    """Top-k nodes by total degree (handy for 'did you mean?' fallback)."""
    deg = [(d, nid) for nid, d in G.degree()]
    deg.sort(key=lambda p: (-p[0], p[1]))
    return [nid for _, nid in deg[:k]]


def answer(
    G: nx.DiGraph,
    question: str,
    depth: int = 3,
    budget: int = 2000,
    strategy: str = "bfs",
) -> str:
    """Return a budgeted subgraph rendering that answers `question`."""
    terms = _terms(question)
    if not terms:
        return "No usable terms in question. Try keywords from the codebase."
    seeds = _seeds(G, terms)
    if not seeds:
        suggestions = _god_nodes(G, k=5)
        lines = [f"No matching nodes for terms: {', '.join(terms)}"]
        if suggestions:
            lines.append("Did you mean one of these high-degree nodes?")
            for nid in suggestions:
                lines.append(f"  - {nid}")
        return "\n".join(lines)
    walker = _dfs if strategy == "dfs" else _bfs
    order = walker(G, seeds, depth)
    body = _render(G, order, budget)
    header = (
        f"QUESTION: {question}\n"
        f"TERMS: {', '.join(terms)}\n"
        f"SEEDS: {', '.join(seeds[:5])}\n"
        f"DEPTH: {depth} STRATEGY: {strategy} BUDGET: {budget} tokens\n"
    )
    return header + body


def explain(G: nx.DiGraph, node: str) -> str:
    """Show a node and its 1-hop neighbourhood."""
    if not G.has_node(node):
        terms = _terms(node)
        candidates = _seeds(G, terms, k=5) if terms else []
        if not candidates:
            return f"Unknown node: {node}"
        node = candidates[0]
    order = [node]
    for n in G.successors(node):
        order.append(n)
    for n in G.predecessors(node):
        if n not in order:
            order.append(n)
    return f"NODE: {node}\n" + _render(G, order, budget=2000)


def path(G: nx.DiGraph, src: str, dst: str) -> str:
    """Shortest path between two nodes (treating the graph as undirected)."""
    if not G.has_node(src):
        cand = _seeds(G, _terms(src), k=1)
        if cand:
            src = cand[0]
    if not G.has_node(dst):
        cand = _seeds(G, _terms(dst), k=1)
        if cand:
            dst = cand[0]
    if not G.has_node(src) or not G.has_node(dst):
        return f"One or both endpoints not found: {src} -> {dst}"
    UG = G.to_undirected(as_view=True)
    try:
        nodes = nx.shortest_path(UG, src, dst)
    except nx.NetworkXNoPath:
        return f"No path between {src} and {dst}"
    except nx.NodeNotFound as e:
        return f"Node not found: {e}"
    return f"PATH ({len(nodes)} nodes):\n" + _render(G, nodes, budget=2000)


def affected(G: nx.DiGraph, node: str, depth: int = 2) -> str:
    """Reverse traversal — what depends on this node, up to `depth` hops."""
    if not G.has_node(node):
        cand = _seeds(G, _terms(node), k=1)
        if cand:
            node = cand[0]
    if not G.has_node(node):
        return f"Unknown node: {node}"
    visited: set[str] = set()
    order: list[str] = []
    q: deque[tuple[str, int]] = deque([(node, 0)])
    while q:
        cur, d = q.popleft()
        if cur in visited:
            continue
        visited.add(cur)
        order.append(cur)
        if d >= depth:
            continue
        for pred in G.predecessors(cur):
            if pred not in visited:
                q.append((pred, d + 1))
    return f"AFFECTED by {node} (depth {depth}):\n" + _render(G, order, budget=2000)
