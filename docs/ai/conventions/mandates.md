# PkoStat — Working Mandates

Imported from `CLAUDE.md` via `@docs/ai/conventions/mandates.md`. `CLAUDE.md` is the project map; this
file is *how you work*. Code style lives in `python.md`; where it disagrees with this file, this file wins.

## Hard rules

- **Money is never a `float`.** Parsing → `Decimal`; storage and arithmetic → `int` grosze
  (`amount_minor`). Conversion to złoty happens only on output. `float(...)` next to an amount is a bug.
- **The LLM does not compute.** Sums, percentages, trends, forecasts — Python only. The LLM receives
  finished numbers and returns categories or text. Numbers in the report always come from `Stats`, never
  from the LLM response.
- **LLM output only through a pydantic schema** (`format` in Ollama + `model_validate_json`). No regex
  parsing of free text.
- **Bank data never leaves the PC.** The only network flow carrying data is reading/deleting from the
  Supabase buffer. LLM — only Ollama on `localhost`. No cloud APIs, no telemetry, no CDNs in the report.
- **Raw input is immutable.** Code never updates or deletes `raw_notifications` and `csv_rows`.
  Everything derived (`transactions`) must be rebuildable by `rebuild` without loss.
- **Real data stays out of git.** Tests and fixtures use anonymised data only (replace names, account
  numbers, phone numbers). Never commit `.env`, `*.db`, statements, or generated reports.
- **SQL only in `db/`**, parameterised only (`?`), no f-strings in queries. The schema changes only via
  a new `NNN_*.sql` migration; existing migrations are never edited.
- **Dependencies only via `uv add` / `uv add --dev`.** No `pip install`. A new runtime dependency — ask
  first.
- **File size ~200 lines.** Before editing a file that is already larger, stop and propose a split.
  Don't cram code into one-liners to game the count.
- **Zero unprompted changes.** Do only what was asked: no opportunistic refactors, renames, or
  reformatting of untouched code. Noticed a problem — report it, don't silently fix it.

## Checks after edits

Run them and wait for the result; report the actual output:

```bash
uv run ruff format
uv run ruff check --fix
uv run pytest
```

Until roadmap stage 0 is done and ruff/pytest are installed, say so instead of pretending the checks
passed. Never report "done" with failing tests.

A change to parsing, reconciliation or analytics **without a test** is not finished: every new
notification format or CSV row type gets a fixture and a test.

## Workflow

1. **Read first.** `docs/pko-expenses-architecture.md` for anything touching data and flows; then the
   code that will be touched. `Read` before `Edit`, `Grep`/`Glob` to locate code.
2. **Ambiguous — ask** (in Russian). Don't guess, and don't build two versions "just in case".
3. **Non-trivial task** (new module, DB schema change, new data flow) — plan first in plan mode; code
   only after approval.
4. **An architectural decision changed or a new one was made** — update the architecture doc and add a
   row to the decision log (§18) in the same change. Existing log rows are never rewritten; a reversal
   is a new row.
5. **A roadmap item is finished** — tick `[x]` in `docs/ai/roadmap.md` in the same change.
6. Report: what changed, the result of the checks. Then stop.

## Git

Commit rules — `docs/ai/conventions/commits.md`. In short: commit only when explicitly asked, push only
when explicitly asked, `branch`/`checkout`/`reset`/`stash`/`rebase`/`merge` — never on your own initiative.

## Communication

With the user — in Russian. Dry, direct, to the point; no intros, apologies, or restating the task.
Facts, then stop.
