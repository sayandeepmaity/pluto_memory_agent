# Pluto setup tutorial — from `git clone` to your first query

This walk-through gets you from "I just heard about Pluto" to "Claude Code
is answering questions grounded in my project's knowledge graph" in under
ten minutes. It assumes nothing about your setup other than that you have
Python and Claude Code.

The flow has three one-time steps and a per-project step you'll repeat
once per repo. After that, day-to-day life is just: write code, commit,
ask Claude questions.

---

## 1. Prerequisites

Before you start, check you have these:

- **Python 3.10 or newer** — `python3 --version`.
- **Claude Code** — the CLI, desktop app, or one of the IDE extensions.
- **Git** on your `PATH` — `git --version`.
- **pipx** (recommended installer) — if you don't have it:
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  # then restart your shell so pipx ends up on PATH
  ```

On Windows, run all of the bash snippets below in **Git Bash** or **WSL**
— the git hooks pluto writes are bash scripts and won't fire from cmd.exe.

---

## 2. Clone and install pluto (one-time, per machine)

```bash
git clone https://github.com/pluto-graph/pluto.git
cd pluto
pipx install .
pluto --version          # → pluto 0.1.0
```

That's it. `pipx` puts pluto in an isolated venv and exposes the `pluto`
command on your `PATH`, so you can run it from any directory afterwards.

**Other installers** (pick any one):

```bash
uv tool install .        # if you already use uv — fast, isolated
pip install -e .         # if you want to hack on pluto itself
```

**Troubleshooting:** if `pluto --version` returns *command not found*,
your shell hasn't picked up pipx's bin directory yet. Run
`pipx ensurepath` and open a new terminal.

---

## 3. Register the `/pluto` skill with Claude Code (one-time, per machine)

```bash
pluto install
```

This single command does the whole Claude Code integration: it copies
`pluto/skill.md` into `~/.claude/skills/pluto/SKILL.md`. Claude Code reads
that file at session start, sees a skill named `pluto`, and from then on
routes natural-language questions about your codebase through
`pluto query` instead of re-grepping the corpus.

If you had Claude Code already open, **restart it** so it picks up the new
skill. You only ever run `pluto install` once per machine.

**For teammates:** prefer per-project install? Use
`pluto install --project` instead. That writes
`.claude/skills/pluto/SKILL.md` inside the repo, and you commit it. Then
anyone who clones the repo gets the skill automatically.

---

## 4. Pick your scenario

Pluto works the same way for an existing project and a brand-new one,
but the first few lines differ. Jump to whichever fits.

### 4A. Existing project — bring it under the graph

```bash
cd /path/to/existing-project
pluto build .            # first graph; scans the whole tree
pluto hook install       # auto-refresh on every commit (recommended)
```

`pluto build .` walks the project, extracts nodes (files, classes,
functions, imports, headings…) and edges (defines, calls, inherits,
imports, links…), clusters them, writes the graph, generates a report,
and renders an interactive viewer. Expect 30–60 seconds for a
medium-sized repo; nothing is sent to an API — it's pure AST + regex.

You'll get a new `pluto-out/` directory next to your code:

```
pluto-out/
├── graph.json          ← source of truth, commit this
├── GRAPH_REPORT.md     ← human summary (god nodes, communities), commit this
├── graph.html          ← open in any browser for the D3 view, commit this
├── manifest.json       ← build metadata, commit this
├── cache/              ← gitignore
└── .pluto_python       ← gitignore
```

Open `pluto-out/graph.html` in a browser to see your project as a
clickable force-directed graph. Skim `GRAPH_REPORT.md` for the top
"god nodes" — the high-degree functions/classes that most of your code
flows through.

Now ask Claude something. Open Claude Code in this directory and type a
natural-language question:

```
> how does authentication work?
```

Behind the scenes Claude sees `pluto-out/graph.json` exists, follows the
fast-path rule in the skill, runs `pluto query "..."`, and gets back a
budgeted subgraph (~2000 tokens) of the relevant `NODE` and `EDGE` lines.
It answers grounded in those lines and cites them — no full-tree grep.

You can also use the query commands directly from the shell:

```bash
pluto query "how does authentication work"
pluto explain Authenticator          # node + neighbours
pluto path Authenticator lookup_user # shortest path
pluto affected hash_password         # who depends on this?
```

### 4B. Brand-new project — start from scratch

```bash
mkdir my-new-project && cd my-new-project
git init
# create at least one source file:
echo 'def hello(): print("hi")' > main.py
git add . && git commit -m "first"

pluto build .
pluto hook install
```

The graph will be tiny (one node, no edges) — that's expected. Pluto
grows with your code: every commit the hook fires `pluto update .`
silently in the background, so the graph stays current as you write.

---

## 5. The day-to-day loop

After step 4, you don't think about pluto much. The loop is:

1. **You edit code.**
2. **You `git commit`.** The `post-commit` hook installed in step 4 runs
   `pluto update .` — AST-only, free, ~1 second for incremental changes.
3. **You ask Claude a question** about the code (or any teammate does).
   Claude consults the fresh graph via the `/pluto` skill and answers.

Need to refresh without committing? `pluto update .`. Want continuous
refresh while iterating? `pluto watch .` in a side terminal — it
re-runs `update` on any file change.

---

## 6. What to commit, what to gitignore

Add to your project's `.gitignore`:

```
pluto-out/cache/
pluto-out/.pluto_python
```

**Commit the rest of `pluto-out/`** — `graph.json`, `GRAPH_REPORT.md`,
`graph.html`, `manifest.json`, and `callflow.html` if you ever export it.
Committing the graph is the whole point of pluto: when a teammate (or
future you) clones the repo, the persistent memory comes with it.
They don't have to rebuild from scratch, and Claude has a working
knowledge of the codebase from the first session.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `pluto: command not found` | `pipx ensurepath`, then open a new terminal. |
| `/pluto` skill not visible in Claude Code | Restart Claude Code. Verify `~/.claude/skills/pluto/SKILL.md` exists. |
| `pluto hook install` says `refused — already exists and is not pluto-managed` | You already have a `post-commit` hook. Pluto won't clobber it; it prints the line to append manually. |
| `pluto query` says "no graph at pluto-out/graph.json" | Run `pluto build .` first, or set `PLUTO_OUT` to where you put it. |
| The graph looks stale | `pluto update .` (or just `pluto build . --force`). |
| Hook doesn't fire on Windows | Use Git Bash or WSL. The hook scripts are bash. |

---

## 8. Uninstall

To roll everything back:

```bash
pluto hook uninstall       # removes only pluto-managed hooks
pluto uninstall            # removes the user-scope skill
pluto uninstall --purge    # also deletes pluto-out/ in the current directory
pipx uninstall pluto       # finally, remove the binary itself
```

That's the full lifecycle. Welcome to graph-grounded Claude Code.
