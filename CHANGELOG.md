# Changelog

All notable changes to Pluto are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-10

Initial release.

### Added
- `pluto build` — full extraction + clustering + report pipeline.
- `pluto query`, `pluto explain`, `pluto path`, `pluto affected` — graph-driven
  question answering with a token budget.
- `pluto update` — incremental AST-only refresh, no LLM cost.
- `pluto cluster-only` — re-cluster an existing graph.
- `pluto export callflow-html` — Mermaid architecture diagram.
- `pluto install` / `pluto uninstall` — register the `/pluto` Claude Code skill
  in user or project scope.
- `pluto hook install` / `uninstall` / `status` — git post-commit + post-checkout
  hooks that auto-refresh the graph.
- `pluto watch` — file-system watcher (uses `watchdog` when available).
- Python AST extractor plus regex extractors for JavaScript, TypeScript, Go,
  Rust, Java, and Markdown.
- `.plutoignore` support with gitignore fallback.
- `PLUTO_OUT` environment variable to override the output directory.
