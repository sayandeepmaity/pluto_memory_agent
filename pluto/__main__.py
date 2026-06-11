"""Pluto CLI entry point — argparse subcommand dispatcher."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__

STUB_COMMANDS = {
    "add": "URL-based ingest is on the roadmap (v0.3+).",
    "extract": "Standalone extract is on the roadmap.",
    "prs": "PR triage is a separate project; not in v0.1.",
    "global": "Cross-repo global graph is roadmap (v0.6).",
    "merge-graphs": "Graph merging needs a conflict resolution story; roadmap.",
    "clone": "Use `git clone` directly — wrapper is not in v0.1.",
    "check-update": "Self-update check is not in v0.1.",
    "label": "Manual labeling is not in v0.1.",
    "serve": "MCP HTTP serve is roadmap (v0.5).",
    "cursor": "Cursor integration is roadmap.",
    "codex": "Codex integration is roadmap.",
    "gemini": "Gemini CLI integration is roadmap.",
    "aider": "Aider integration is roadmap.",
}


def _output_dir(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    env = os.environ.get("PLUTO_OUT")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / "pluto-out").resolve()


def _write_manifest(out_dir: Path, root: Path, stats: dict) -> None:
    manifest = {
        "pluto_version": __version__,
        "root": str(root),
        "generated_at": int(time.time()),
        "stats": stats,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (out_dir / ".pluto_python").write_text(sys.executable + "\n", encoding="utf-8")


def cmd_build(args: argparse.Namespace) -> int:
    from . import build as build_mod
    from . import cache as cache_mod
    from . import detect, extract

    root = Path(args.path).resolve()
    out_dir = _output_dir(args.out)
    cache_dir = out_dir / "cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    files = detect.collect_files(root)
    print(f"pluto: scanning {root}", file=sys.stderr)
    print(f"pluto: {len(files)} candidate files", file=sys.stderr)
    extractions: list[dict] = []
    cache_hits = 0
    for path, _kind in files:
        cached = cache_mod.load(path, cache_dir)
        if cached is not None:
            extractions.append(cached)
            cache_hits += 1
            continue
        ex = extract.extract(path, root)
        if ex:
            cache_mod.save(path, cache_dir, ex)
            extractions.append(ex)
    print(f"pluto: cache hits {cache_hits}/{len(files)}", file=sys.stderr)

    G = build_mod.build(extractions)

    graph_path = out_dir / "graph.json"
    if graph_path.exists() and not args.force:
        try:
            prior = build_mod.load(graph_path)
            if prior.number_of_nodes() > G.number_of_nodes() * 1.5:
                print(
                    f"pluto: new graph ({G.number_of_nodes()} nodes) is much smaller than "
                    f"existing ({prior.number_of_nodes()}). Re-run with --force to overwrite.",
                    file=sys.stderr,
                )
                return 1
        except Exception:
            pass

    communities: dict[int, list[str]] = {}
    if not args.no_cluster:
        from . import cluster as cluster_mod

        communities = cluster_mod.cluster(G)
        cluster_mod.attach_communities(G, communities)

    build_mod.save(G, graph_path)

    from . import analyze, report

    analysis = {
        "god_nodes": analyze.god_nodes(G, top_n=20),
        "surprises": analyze.surprises(G, communities) if communities else [],
        "suggested_questions": analyze.suggest_questions(G, communities),
    }
    report_text = report.generate(G, communities, analysis)
    report.write(out_dir / "GRAPH_REPORT.md", report_text)

    if not args.no_viz:
        from . import export

        html = export.to_html(G, communities)
        (out_dir / "graph.html").write_text(html, encoding="utf-8")

    _write_manifest(out_dir, root, {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "communities": len(communities),
        "files_scanned": len(files),
        "cache_hits": cache_hits,
    })
    print(
        f"pluto: built {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{len(communities)} communities → {out_dir}"
    )
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Incremental rebuild — same as build, just reuses cache and skips viz unless asked."""
    from . import build as build_mod
    from . import cache as cache_mod
    from . import detect, extract

    root = Path(args.path).resolve()
    out_dir = _output_dir(None)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    files = detect.collect_files(root)
    extractions: list[dict] = []
    changed = 0
    for path, _kind in files:
        cached = cache_mod.load(path, cache_dir)
        if cached is not None:
            extractions.append(cached)
            continue
        ex = extract.extract(path, root)
        if ex:
            cache_mod.save(path, cache_dir, ex)
            extractions.append(ex)
            changed += 1

    G = build_mod.build(extractions)

    communities: dict[int, list[str]] = {}
    if not args.no_cluster:
        from . import cluster as cluster_mod

        communities = cluster_mod.cluster(G)
        cluster_mod.attach_communities(G, communities)

    build_mod.save(G, out_dir / "graph.json")
    _write_manifest(out_dir, root, {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "communities": len(communities),
        "files_scanned": len(files),
        "changed_files": changed,
    })
    print(
        f"pluto: updated {G.number_of_nodes()} nodes, {G.number_of_edges()} edges "
        f"({changed} files changed)"
    )
    return 0


def cmd_cluster_only(args: argparse.Namespace) -> int:
    from . import build as build_mod
    from . import cluster as cluster_mod

    graph_path = Path(args.graph) if args.graph else _output_dir(None) / "graph.json"
    if not graph_path.exists():
        print(f"pluto: no graph at {graph_path}. Run `pluto build` first.", file=sys.stderr)
        return 1
    G = build_mod.load(graph_path)
    communities = cluster_mod.cluster(G, resolution=args.resolution)
    cluster_mod.attach_communities(G, communities)
    build_mod.save(G, graph_path)
    print(f"pluto: re-clustered into {len(communities)} communities → {graph_path}")
    return 0


def _load_graph_for_query(graph_arg: str | None):
    from . import build as build_mod

    graph_path = Path(graph_arg) if graph_arg else _output_dir(None) / "graph.json"
    if not graph_path.exists():
        print(
            f"pluto: no graph at {graph_path}. Run `pluto build .` first.",
            file=sys.stderr,
        )
        return None
    return build_mod.load(graph_path)


def cmd_query(args: argparse.Namespace) -> int:
    from . import query as query_mod

    G = _load_graph_for_query(args.graph)
    if G is None:
        return 1
    strategy = "dfs" if args.dfs else "bfs"
    print(query_mod.answer(G, args.question, depth=args.depth, budget=args.budget, strategy=strategy))
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    from . import query as query_mod

    G = _load_graph_for_query(args.graph)
    if G is None:
        return 1
    print(query_mod.explain(G, args.node))
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    from . import query as query_mod

    G = _load_graph_for_query(args.graph)
    if G is None:
        return 1
    print(query_mod.path(G, args.a, args.b))
    return 0


def cmd_affected(args: argparse.Namespace) -> int:
    from . import query as query_mod

    G = _load_graph_for_query(args.graph)
    if G is None:
        return 1
    print(query_mod.affected(G, args.node, depth=args.depth))
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    from . import install as install_mod

    info = install_mod.install(project=args.project)
    print(f"pluto: skill installed at {info['path']} (scope: {info['scope']})")
    if info.get("replaced"):
        print("pluto: (replaced existing SKILL.md)")
    if info.get("hint"):
        print(f"pluto: {info['hint']}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    from . import install as install_mod

    info = install_mod.uninstall(project=args.project, purge=args.purge)
    print(f"pluto: skill {'removed' if info['removed'] else 'not present'} ({info['path']})")
    if info["purged"]:
        print("pluto: pluto-out/ purged")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    from . import hooks

    if args.hook_action == "install":
        try:
            info = hooks.install_hooks()
        except FileNotFoundError as e:
            print(f"pluto: {e}", file=sys.stderr)
            return 1
        for name, result in info["hooks"].items():
            print(f"pluto: {name}: {result}")
        return 0
    if args.hook_action == "uninstall":
        info = hooks.uninstall_hooks()
        for name, result in info["hooks"].items():
            print(f"pluto: {name}: {result}")
        return 0
    if args.hook_action == "status":
        info = hooks.status()
        print(json.dumps(info, indent=2))
        return 0
    print(f"pluto: unknown hook action {args.hook_action}", file=sys.stderr)
    return 2


def cmd_export(args: argparse.Namespace) -> int:
    from . import build as build_mod
    from . import export

    if args.export_kind != "callflow-html":
        print(f"pluto: unknown export kind {args.export_kind}", file=sys.stderr)
        return 2
    out_dir = _output_dir(None)
    graph_path = out_dir / "graph.json"
    if not graph_path.exists():
        print(f"pluto: no graph at {graph_path}. Run `pluto build` first.", file=sys.stderr)
        return 1
    G = build_mod.load(graph_path)
    html = export.to_callflow_html(G, max_sections=args.max_sections)
    dest = Path(args.output) if args.output else out_dir / "callflow.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    print(f"pluto: wrote callflow → {dest}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    out_dir = _output_dir(None)
    graph_path = out_dir / "graph.json"
    print(f"pluto: watching {root}. Ctrl-C to stop.")

    def _rebuild() -> None:
        ns = argparse.Namespace(path=str(root), no_cluster=False)
        cmd_update(ns)

    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore
        from watchdog.observers import Observer  # type: ignore
    except ImportError:
        last = {}
        try:
            from . import detect
            while True:
                files = detect.collect_files(root)
                changed = False
                for path, _ in files:
                    try:
                        m = path.stat().st_mtime
                    except OSError:
                        continue
                    if last.get(path) != m:
                        last[path] = m
                        changed = True
                if changed:
                    _rebuild()
                    print(f"pluto: rebuilt → {graph_path}")
                time.sleep(2.0)
        except KeyboardInterrupt:
            return 0

    class _Handler(FileSystemEventHandler):
        def __init__(self) -> None:
            self.dirty = False
            self.last = 0.0

        def on_any_event(self, event) -> None:
            if event.is_directory:
                return
            self.dirty = True

    handler = _Handler()
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1.0)
            now = time.time()
            if handler.dirty and now - handler.last > 1.0:
                handler.dirty = False
                handler.last = now
                _rebuild()
                print(f"pluto: rebuilt → {graph_path}")
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
    return 0


def cmd_stub(args: argparse.Namespace) -> int:
    msg = STUB_COMMANDS.get(args.subcommand, "Not yet implemented.")
    print(f"pluto: `{args.subcommand}` is not yet implemented.")
    print(f"  {msg}")
    print("  See the roadmap: https://github.com/pluto-graph/pluto#roadmap")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pluto", description="Pluto knowledge-graph CLI.")
    p.add_argument("--version", action="version", version=f"pluto {__version__}")
    sub = p.add_subparsers(dest="command")

    pb = sub.add_parser("build", help="Build the full graph (extract + cluster + report + viz).")
    pb.add_argument("path", nargs="?", default=".")
    pb.add_argument("--no-viz", action="store_true", help="Skip graph.html.")
    pb.add_argument("--no-cluster", action="store_true", help="Skip Louvain clustering.")
    pb.add_argument("--out", default=None, help="Override pluto-out/ location.")
    pb.add_argument("--force", action="store_true", help="Overwrite even if new graph is smaller.")
    pb.set_defaults(func=cmd_build)

    pu = sub.add_parser("update", help="Incremental rebuild (AST-only, free).")
    pu.add_argument("path", nargs="?", default=".")
    pu.add_argument("--force", action="store_true")
    pu.add_argument("--no-cluster", action="store_true")
    pu.set_defaults(func=cmd_update)

    pc = sub.add_parser("cluster-only", help="Re-cluster the existing graph.json.")
    pc.add_argument("path", nargs="?", default=".")
    pc.add_argument("--resolution", type=float, default=1.0)
    pc.add_argument("--graph", default=None)
    pc.set_defaults(func=cmd_cluster_only)

    pq = sub.add_parser("query", help="BFS over the graph and return a budgeted subgraph.")
    pq.add_argument("question")
    pq.add_argument("--dfs", action="store_true")
    pq.add_argument("--depth", type=int, default=3)
    pq.add_argument("--budget", type=int, default=2000)
    pq.add_argument("--graph", default=None)
    pq.set_defaults(func=cmd_query)

    pe = sub.add_parser("explain", help="Show a node and its immediate neighbours.")
    pe.add_argument("node")
    pe.add_argument("--graph", default=None)
    pe.set_defaults(func=cmd_explain)

    pp = sub.add_parser("path", help="Shortest path between two nodes.")
    pp.add_argument("a")
    pp.add_argument("b")
    pp.add_argument("--graph", default=None)
    pp.set_defaults(func=cmd_path)

    pa = sub.add_parser("affected", help="What depends on this node (reverse traversal).")
    pa.add_argument("node")
    pa.add_argument("--depth", type=int, default=2)
    pa.add_argument("--graph", default=None)
    pa.set_defaults(func=cmd_affected)

    pi = sub.add_parser("install", help="Install the /pluto Claude Code skill.")
    pi.add_argument("--project", action="store_true", help="Install in ./.claude/ instead of ~/.claude/.")
    pi.set_defaults(func=cmd_install)

    pun = sub.add_parser("uninstall", help="Uninstall the /pluto skill.")
    pun.add_argument("--purge", action="store_true", help="Also delete pluto-out/.")
    pun.add_argument("--project", action="store_true")
    pun.set_defaults(func=cmd_uninstall)

    ph = sub.add_parser("hook", help="Manage git hooks that auto-refresh the graph.")
    ph.add_argument("hook_action", choices=["install", "uninstall", "status"])
    ph.set_defaults(func=cmd_hook)

    pex = sub.add_parser("export", help="Export auxiliary views.")
    pex.add_argument("export_kind", choices=["callflow-html"])
    pex.add_argument("--output", default=None)
    pex.add_argument("--max-sections", type=int, default=5)
    pex.set_defaults(func=cmd_export)

    pw = sub.add_parser("watch", help="Re-run `pluto update` on file changes.")
    pw.add_argument("path", nargs="?", default=".")
    pw.set_defaults(func=cmd_watch)

    for name in STUB_COMMANDS:
        sp = sub.add_parser(name, help=f"(stub) {STUB_COMMANDS[name]}")
        sp.set_defaults(func=cmd_stub, subcommand=name)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
