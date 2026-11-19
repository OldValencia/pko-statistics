# PkoStat — Roadmap

Stages go in order; each ends with something you can **run and see**. Tick `[x]` in the same change
that completes the item. Decisions and their reasons live in the decision log,
`docs/pko-expenses-architecture.md` §18.

## Stage 0. Foundation
- [x] Move the code into the `src/pkostat/` package, `pkostat` entry point in `pyproject.toml`, `tests/` at the root.
- [x] Dev dependencies: `ruff`, `pytest`. Ruff settings in `pyproject.toml`.
- [x] `config.py`: `.env` + environment variables, `PKOSTAT_HOME` (default `~/pkostatistics`).
- [x] SQLite: connection, migrations `NNN_*.sql` + `PRAGMA user_version`.
- [x] `.gitignore`: `.env`, `*.db`, real statements (`docs/examples/`).
- [x] Delete the old draft `src/main/` and `src/tests/`.

**Done when:** `uv run pkostat --help` works, `uv run pytest` is green, the database gets created.

## Stage 1. Users and push intake
- [x] `pkostat user add|list|rotate`, importing the existing UUID via `--token`.
- [x] Supabase: insert-only RLS for anon; the Shortcut uses the publishable key.
- [x] `pkostat sync`: pagination, storing by `remote_id`, deleting after commit, `rejected_notifications`.
- [x] Verified on a real push (see Done when).

**Done when:** a real push from the phone is in the local database after `sync` and gone from Supabase.

## Stage 2. Notification parsing
- [x] Parsers for `Payment card authorization`, `Account debit`, `Account credit`; `unparsed` for the rest.
- [x] Anonymised fixtures from `docs/examples/notifications/` + tests for each type.
- [x] `pkostat rebuild` builds `transactions` from `raw_notifications`; unrecognised headers are listed.
- [x] `display_name` for users (`user add --display-name`, `user display-name`).

**Done when:** all examples parse and the amounts in grosze match.

## Stage 3. CSV import and reconciliation
- [x] `pkostat import-csv`: cp1250, `Key: value` parsing, skipping `Blokada`, `row_key`, protection
      against re-importing a file and overlapping periods.
- [x] Push ↔ CSV reconciliation: `superseded` / `unmatched` / `pending`.
- [x] Verified on the real export: 1599 settled rows, monthly sums equal `Kwota` to the grosz.

**Done when:** the sample statement imports, a repeat import adds nothing, and the monthly total matches
the sum of `Kwota` in the CSV.

## Stage 4. Categories (no LLM)
- [x] Merchant normalisation (`WOLT`, `BOLT`, `ZABKA`, `ALLEGRO`, `UBER` …); reconciliation uses it.
- [x] `categories.toml` (list + `kind`), `rules.toml` (defaults by kind, title rules, merchant rules),
      created by `init`, validated on load.
- [x] `pkostat category list|set|unset`, `pkostat uncategorized`; categories assigned on rebuild.
- [x] `transaction_overrides` honoured by the categoriser.
- [x] Overriding one transaction — in the UI (Transactions page), not as a command.
- [x] Merchants with two usual categories (`alternative` in `rules.toml`; Wolt: food delivery or
      groceries — the bank data cannot tell them apart; Allegro: household & pets or marketplace): a one-tap switch per operation. Manual
      overrides follow a push or hold to the statement row that replaces it.

## Stage 5. Local app and the report
Day-to-day use moves from CLI commands to a local website; the CLI stays for automation and dev.
See architecture §11.

- [ ] Mockup first: static HTML of the report page and the transactions page on real numbers,
      reviewed by the user before any of it is coded.
- [x] App: `uv run pkostat` (= `pkostat serve`) starts FastAPI on 127.0.0.1:8765 and opens the
      browser; the same report template in admin mode; edits via a JSON API called with `fetch`,
      then a reload that keeps page, filters, month and scroll. Host + Origin + X-PkoStat checks.
- [x] Transactions page: change the category of one operation (override) or of every operation of
      the merchant (rule).
- [x] Uncategorised page: merchants grouped, biggest money first, one dropdown each.
- [x] Categories page: label, kind, description, month shift; add; delete when unused; list and
      delete stored merchant rules. Categories stay in `categories.toml` (rewritten by the app with
      a fixed header); `name` never changes, so rules keep working.
- [x] Data page: CSV upload, Sync, Rebuild, import history, status counts.
- [x] Users page: add, display name, show/copy/rotate token.
- [x] Share link per user (`share_id`) — with publishing, stage 9.
- [ ] Rule files: packaged default merchant rules still reach the user only through `init`
      (the copied `rules.toml` does not get new defaults). Revisit if it starts to hurt.
- [x] Russian UI: category `label` (Russian) next to the stable `name`, plural helper, no gendered
      verbs about the user. Bank data shown as received.
- [ ] Two audiences: admin (local app, everything) and user (read-only HTML with only that user's
      data: Report + Transactions without editing).
- [x] `analytics`: months, categories, kinds, comparison with previous month and 3-month baseline,
      leaks/wins, share, pace by day, impulse by weekday, top merchants, recurring payments, year to
      date, what-if levers. Month shift per category (`month_shift_from_day`, rent = 25).
- [ ] **The report — a fixed template, designed once.** The LLM never writes HTML or chooses the
      layout: the code fills the template with `Stats`, the LLM (stage 6) only fills named text
      slots (summary, leaks, recommendations, praise), placeholders when it did not run. Goal — an
      analyser, not a dashboard: one glance answers *where did I screw up, where did I do well,
      compared to last month and to my limits*; each section states a verdict with its number.
- [x] Mockup v2 approved by the owner ("10/10"). Section list: architecture §11.
- [x] Mockup turned into the Jinja2 template (`report/templates`, `report/static`); numbers from
      `analytics`, LLM text slots show a placeholder until stage 6.
- [x] `pkostat report --user U [--out F] [--open]`: the read-only user HTML, self-contained,
      untrusted text escaped (`<` → `\u003c` in the embedded JSON).

**Done when:** everything done today with `category set`, `uncategorized`, `import-csv`, `sync`,
`user …` can be done in the browser; the report matches the reviewed mockup, works offline and
shows the same numbers as `analytics` in tests.

## Stage 6. LLM — reduced to suggestions, after measuring it
- [x] Ollama client: structured output from a pydantic schema, `num_ctx` 16k, `think` low/medium,
      one retry on an answer that does not fit the schema, readable errors.
- [x] Measured on real data. Merchant categories, blind test on 135 known merchants: 59 % right,
      64 % with the owner's own choices as examples and `think: medium`; one confident answer in
      five still wrong. Month texts for all 11 months: drops told as "the reason for growth",
      advice contradicting its own plan, a running month judged as finished.
- [x] Merchant categories are **suggestions** (`llm_suggestions`), never applied by themselves:
      pre-selected on the Uncategorised page with the model's confidence, saved by the owner
      ("Сохранить" / "Сохранить все выбранные"). `pkostat categorize`, `pkostat run`, a button.
- [x] Month summary and recommendations are **built by code** (`analytics/story.py`,
      `analytics/advice.py`): verdict, what moved spending most vs the previous month, the goal,
      one piece of good news; advice = back within a limit / back to the usual level / no more
      than 10 times a month, each saving computed from that month. The LLM text feature, its
      prompt and its table were removed (migration 007).
- [ ] Optional: web search for unknown merchants through Ollama's web search API (needs an
      ollama.com API key; merchant names leave the PC) — only on a button, never in `run`.

## Stage 7. Budgets and goals (optional)
- [x] Plan per user in the database (`goals`, `budgets`), edited on the admin "Бюджеты" page:
      monthly saving goal, per-category limits, "average −10/25%" helpers.
- [x] In the report: limits with spent / limit / forecast (running month), status with icon and
      words, overspend amount; goal met or not (complete month) or "can still spend X, Y a day"
      (running month, usual income until salary arrives). Hidden without a plan.
- [x] The LLM sees the plan (goal met, categories over and near the limit).

## Stage 8. Convenience
- [x] `pkostat run` (= "Обновить всё" on the Data page): sync → rebuild → LLM merchants → LLM
      text for the last complete and the running month when missing or stale → user reports →
      backup. A failing step is reported, the rest still runs; exit code 1 if any step failed.
- [x] `pkostat backup [--list]`, `pkostat restore FILE`: zip with a SQLite snapshot and the two
      TOML files, never `.env`; 30 kept; `PKOSTAT_BACKUP_DIR` for a cloud-synced folder; a daily
      backup when the app starts. Restore checks integrity and saves the current state first.
- [x] Month-over-month comparison on the report's first screen (done in stage 5).
- [x] `run-daily.bat` for Windows Task Scheduler, log in `<data folder>\logs\run.log`:
      `schtasks /Create /TN "PkoStat daily" /SC DAILY /ST 21:00 /TR "\"D:\Projects\pkostatistics\run-daily.bat\""`
      (the PC must be on at that time; Ollama must be running for the LLM steps).

## Stage 9. Report in the cloud
- [x] Publish each shared user's read-only HTML, encrypted, to GitHub Pages of this repository
      (`gh-pages`, one fresh commit per publish) at `<site>/<share_id>/` (architecture §16).
      Random `share_id` and password per user (migration 008), separate from the push token.
- [x] Users page: open access, copy link (password in the fragment), new link, close; "Опубликовать
      сейчас". `pkostat user share NAME [--off]`, `pkostat publish [--force]`; a step of `run`.
- [x] Push only on change (`publish-state.json`); `run-publish.bat` for Task Scheduler every 2 h:
      `schtasks /Create /TN "PkoStat publish" /SC HOURLY /MO 2 /TR "\"D:\Projects\pkostatistics\run-publish.bat\""`
