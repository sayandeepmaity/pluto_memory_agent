"""HTML viewers: a single-file D3 graph and a Mermaid callflow diagram."""

from __future__ import annotations

import html
import json

import networkx as nx

_GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pluto Graph</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #0e1117; color: #e6edf3;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  #info { position: fixed; top: 0; left: 0; padding: 8px 12px; background: rgba(0,0,0,0.6);
          font-size: 12px; max-width: 360px; pointer-events: none; }
  svg { width: 100vw; height: 100vh; display: block; cursor: grab; }
  .node circle { stroke: #fff; stroke-width: 1px; }
  .node text { font-size: 9px; fill: #c9d1d9; pointer-events: none; }
  .link { stroke: #58a6ff; stroke-opacity: 0.25; stroke-width: 1px; }
</style>
</head>
<body>
<div id="info">__INFO__</div>
<svg></svg>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const DATA = __DATA__;
const svg = d3.select("svg");
const width = window.innerWidth;
const height = window.innerHeight;
const g = svg.append("g");

svg.call(d3.zoom().on("zoom", (ev) => g.attr("transform", ev.transform)));

const palette = d3.schemeTableau10;
const colorFor = (c) => palette[(c == null ? 0 : c) % palette.length];

const sim = d3.forceSimulation(DATA.nodes)
  .force("link", d3.forceLink(DATA.links).id(d => d.id).distance(40))
  .force("charge", d3.forceManyBody().strength(-80))
  .force("center", d3.forceCenter(width/2, height/2))
  .force("collide", d3.forceCollide(8));

const link = g.append("g").selectAll("line")
  .data(DATA.links).join("line").attr("class", "link");

const node = g.append("g").selectAll("g")
  .data(DATA.nodes).join("g").attr("class", "node")
  .call(d3.drag()
    .on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart();
                              d.fx = d.x; d.fy = d.y; })
    .on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
    .on("end", (ev, d) => { if (!ev.active) sim.alphaTarget(0);
                            d.fx = null; d.fy = null; }));

node.append("circle")
  .attr("r", d => 4 + Math.min(d.degree || 1, 12))
  .attr("fill", d => colorFor(d.community));

node.append("title").text(d => `${d.id}\\ntype=${d.type}\\ncommunity=${d.community}`);
node.append("text").attr("dx", 6).attr("dy", 3).text(d => d.name || d.id);

sim.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${d.x},${d.y})`);
});
</script>
</body>
</html>
"""


def to_html(G: nx.DiGraph, communities: dict[int, list[str]] | None = None) -> str:
    """Build a self-contained D3 viewer (CDN-loaded D3, no build step)."""
    node_to_comm: dict[str, int] = {}
    if communities:
        for cid, members in communities.items():
            for nid in members:
                node_to_comm[nid] = cid

    nodes = []
    for nid, attrs in G.nodes(data=True):
        nodes.append({
            "id": nid,
            "name": attrs.get("name", nid),
            "type": attrs.get("type", "?"),
            "community": node_to_comm.get(nid, attrs.get("community")),
            "degree": G.degree(nid),
            "src": attrs.get("src"),
        })
    links = []
    for s, t, attrs in G.edges(data=True):
        links.append({
            "source": s,
            "target": t,
            "type": attrs.get("type", "edge"),
        })
    data = {"nodes": nodes, "links": links}
    info = html.escape(
        f"Pluto graph — {len(nodes)} nodes, {len(links)} edges, "
        f"{len(communities) if communities else 0} communities. "
        f"Drag a node, scroll to zoom."
    )
    return (_GRAPH_HTML_TEMPLATE
            .replace("__DATA__", json.dumps(data))
            .replace("__INFO__", info))


_MERMAID_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pluto Callflow</title>
<style>
  body { background: #0e1117; color: #e6edf3; font-family: sans-serif;
         margin: 0; padding: 16px; }
  pre.mermaid { background: #161b22; padding: 12px; border-radius: 6px;
                overflow: auto; }
</style>
</head>
<body>
<h1>Pluto Callflow</h1>
<p>__SUMMARY__</p>
<pre class="mermaid">
__DIAGRAM__
</pre>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "dark" });
</script>
</body>
</html>
"""


def _mermaid_id(nid: str) -> str:
    """Mermaid node IDs must match `[A-Za-z][A-Za-z0-9_]*`."""
    safe = []
    for ch in nid:
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        else:
            safe.append("_")
    out = "".join(safe)
    if not out or not out[0].isalpha():
        out = "n_" + out
    return out[:64]


def to_callflow_html(G: nx.DiGraph, max_sections: int = 5) -> str:
    """Produce a Mermaid `graph TD` view focused on the highest-degree nodes."""
    deg = sorted(G.degree(), key=lambda p: -p[1])
    top = [nid for nid, _ in deg[: max(20, max_sections * 8)]]
    top_set = set(top)
    seen_labels: dict[str, str] = {}
    lines = ["graph TD"]
    for nid in top:
        attrs = G.nodes[nid]
        label = attrs.get("name", nid)
        mid = _mermaid_id(nid)
        if mid in seen_labels:
            continue
        seen_labels[mid] = label
        safe_label = label.replace('"', "'")
        lines.append(f'    {mid}["{safe_label}"]')
    for s, t, attrs in G.edges(data=True):
        if s in top_set and t in top_set:
            etype = attrs.get("type", "")
            sid = _mermaid_id(s)
            tid = _mermaid_id(t)
            arrow = f"-->|{etype}|" if etype else "-->"
            lines.append(f"    {sid} {arrow} {tid}")
    diagram = "\n".join(lines)
    summary = html.escape(
        f"{G.number_of_nodes()} nodes total, focused view of top {len(seen_labels)} by degree."
    )
    return (_MERMAID_TEMPLATE
            .replace("__DIAGRAM__", diagram)
            .replace("__SUMMARY__", summary))
