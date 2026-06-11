# Pluto

A Claude-Code-only CLI that turns any project into a queryable knowledge graph.
Build the graph once (AST + regex, zero tokens), query it forever with
~70× fewer tokens per question.

## Install

```bash
git clone https://github.com/pluto_memory_agent/pluto
cd pluto
uv tool install .        # or: pipx install . / pip install -e .
pluto --version          # pluto 0.1.0
```

## Quickstart

```bash
cd /path/to/your/project
pluto install            # register /pluto with Claude Code (user scope)
pluto hook install       # auto-rebuild on every git commit
pluto build .            # build the first graph
```

Then inside Claude Code:

```
/pluto
You: how does authentication work?
```

Claude runs `pluto query "..."`, gets a budgeted subgraph (default 2000
tokens), and answers grounded in node/edge evidence — without re-reading
the whole tree.

> New to pluto? Walk through the full setup in [docs/tutorial.md](docs/tutorial.md).

## What lands in `pluto-out/`

```
pluto-out/
├── graph.json          # nx.DiGraph in node-link JSON (commit this)
├── GRAPH_REPORT.md     # human + agent summary (commit this)
├── graph.html          # interactive D3 viewer (commit this)
├── callflow.html       # Mermaid architecture (commit this, when exported)
├── manifest.json       # build metadata (commit this)
├── cache/              # per-file extraction cache (gitignore)
└── .pluto_python       # interpreter path used to build (gitignore)
```

## Top-level commands

```
pluto build [path]                   # full pipeline
pluto update [path]                  # incremental, AST-only
pluto cluster-only [path]            # re-cluster existing graph
pluto query "<question>"             # BFS over graph, budgeted
pluto explain "<node>"               # node + neighbours
pluto path "<a>" "<b>"               # shortest path
pluto affected "<node>"              # reverse impact
pluto watch [path]                   # auto-rebuild on changes
pluto install [--project]            # install /pluto skill
pluto uninstall [--purge|--project]
pluto hook install|uninstall|status  # git hooks
pluto export callflow-html           # Mermaid architecture
pluto --version
```

See `docs/commands.md` for the full reference.

## Environment

- `PLUTO_OUT` — override the output directory (default: `pluto-out`).

## License

MIT.
