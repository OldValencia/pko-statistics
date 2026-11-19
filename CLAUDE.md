# PkoStat

A personal spending analyser for a PKO BP account, for 1–2 people. IKO push notifications (via iOS
Shortcut → Supabase buffer) and iPKO CSV statements are collected into a **local** SQLite database;
Python computes the statistics; a local LLM (Ollama, `gpt-oss:20b`) categorises merchants and writes
recommendations; the output is a self-contained HTML report. The goal is to understand where the money
goes and start saving.

@docs/ai/conventions/mandates.md

## Where to read what

| File | Why |
| --- | --- |
| `docs/ai/general_idea.md` | what we're building, for whom, what we don't do |
| `docs/pko-expenses-architecture.md` | data flows, DB schema, push ↔ CSV reconciliation, LLM role, decision log |
| `docs/ai/roadmap.md` | stages and what's done |
| `docs/ai/conventions/python.md` | how to write code |
| `docs/ai/conventions/commits.md` | commits and pushes |
| `docs/examples/notifications/` | real push texts by type (local only, gitignored) |
| `docs/examples/fin-audit-html/` | sample CSV statement (cp1250) and the report's visual reference (local only, gitignored) |

## State

Stages 0-4 are done: package, config, migrations, users (`user add|list|rotate|display-name`),
`sync` (verified on real pushes), notification parsers, `import-csv` (verified on the real export),
push <-> statement reconciliation, `rebuild`, categories (`categories.toml`, `rules.toml`,
`category set`, `uncategorized`). Stage 5 done: `analytics`, the approved report template,
`pkostat report` (read-only user HTML) and the local admin website (`uv run pkostat`, `run.bat`).
Stage 6 done and narrowed after measuring: the local LLM only suggests categories for unknown
merchants (owner confirms); month summary and advice are built by code (`analytics/story.py`). Stage 7 done: per-user saving goal
and category limits edited in the app, shown in the report. Stage 8 done: `pkostat run` /
"Обновить всё", backups (`pkostat backup|restore`, daily on app start), `run-daily.bat` for Task
Scheduler. Stage 9 done: shared users' reports are published encrypted to GitHub Pages (`gh-pages`
of this public repository; `pkostat publish`, `run-publish.bat`). Everything on the roadmap is done.

## Commands

```bash
uv sync                      # environment
uv run pkostat --help        # CLI
uv run pkostat init          # create ~/pkostatistics, .env template, configs, database
uv run pkostat              # the admin website on http://127.0.0.1:8765 (or run.bat)
uv run pkostat run          # everything: sync, rebuild, LLM, reports, backup (run-daily.bat)
uv run pkostat report --user jane --open   # read-only report HTML
uv run pkostat publish       # encrypted reports to GitHub Pages, only if something changed
uv run pytest                # tests
uv run ruff format && uv run ruff check --fix
ollama list                  # gpt-oss:20b must be present
```

## Environment

- Windows 11, PowerShell; Python 3.14 via uv.
- User data lives in `~/pkostatistics/` (`PKOSTAT_HOME`): database, `.env`, configs, reports, backups.
  None of it is in the repository, and it must stay that way.
- Secrets: `SUPABASE_SECRET_KEY` is local only. The iOS Shortcut gets only the publishable key.
