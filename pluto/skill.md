---
name: pluto
description: "Use for any question about the codebase, its architecture, or file relationships — especially when pluto-out/ exists, where the question should be treated as a pluto query first. Turns any folder into a persistent knowledge graph with god nodes and BFS query."
---

# /pluto

## Fast path — graph already exists
If `pluto-out/graph.json` exists AND the user's request is a
natural-language question (not an explicit rebuild command):
  - Run `pluto query "<question>"` immediately.
  - Cite `NODE` lines from the output as evidence.
  - Do NOT walk the file tree.

## Slow path — first run or explicit rebuild
1. Detect platform Python (uv tool / pipx / system).
2. Run `pluto build <path>` (default: current working directory).
3. Print a one-line summary of node/edge counts.
4. Suggest `pluto hook install` if `.git/hooks/post-commit` is missing.

## Sub-commands the assistant can invoke
- `pluto query "..."` — BFS, default 2000-token budget.
- `pluto explain "..."` — node + neighbours.
- `pluto path "A" "B"` — shortest path between two nodes.
- `pluto affected "..."` — reverse impact (what depends on this).
- `pluto update .` — incremental refresh (free).

## Rules
- After modifying code in this session, run `pluto update .`.
- If the graph doesn't answer cleanly, fall back to reading only the
  specific files in the `src=...` fields, never the whole tree.
- Never re-grep the corpus when a graph query will do.
