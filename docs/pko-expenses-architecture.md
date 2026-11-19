# PkoStat — Architecture

**Status:** design; the code has never been run (`src/main/` is a draft and will be rewritten).
**Updated:** 18 November 2026.
**Purpose:** a personal tool for 1–2 people. Collect PKO BP transactions (IKO push notifications + CSV
statements), store them **locally**, compute statistics in plain code, give a local LLM (Ollama) only
aggregates for categorisation and recommendations, and generate a self-contained HTML report.

The goal is not "pretty charts" but an answer to **"where does the money go, and what exactly should I
cut to start saving"**. More in `docs/ai/general_idea.md`.

---

## 1. Overview

```text
iPhone (IKO push → iOS Shortcut)          iPKO CSV statement (manual, monthly/quarterly)
        │ HTTPS POST (publishable key)                     │
        ▼                                                  │
Supabase: notifications table                              │
(inbound buffer ONLY, insert-only)                         │
        │ pkostat sync (secret key):                       │
        │ read → store locally → delete                    │
        ▼                                                  ▼
┌──────────────────────── Local PC: pkostat (Python, uv) ────────────────────────────┐
│                                                                                     │
│  SQLite (~/pkostatistics/db/pkostat.db)  — the single source of truth              │
│   raw_notifications, csv_rows  (raw input, never modified)                          │
│   transactions                 (normalised, rebuilt from raw input)                 │
│   merchant_rules, users, reports …                                                  │
│                                                                                     │
│  parse → reconcile → categorize ──(unknown merchants)──► Ollama (gpt-oss:20b)      │
│                          │                                                          │
│                     analytics (pure Python, Decimal/grosze)                         │
│                          │                                                          │
│                          ├──(aggregates JSON)──► Ollama: insights & recommendations │
│                          ▼                                                          │
│                  Jinja2 → reports/<user>/<period>.html  (single file, offline)      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                           │  (later, stage 9)
                           ▼
                 publish the report to the cloud behind authentication
```

**Principles:**

1. **The cloud is only a mailbox.** Supabase keeps a notification only until the next `pkostat sync`.
   CSVs, transactions, categories, budgets and reports never go to the cloud.
2. **Raw input is immutable; everything else is rebuildable.** The original notification text and the
   original CSV row are stored as-is. Improved a parser or category rules → `pkostat rebuild`
   recomputes `transactions` from raw input without losing anything.
3. **The LLM does not do money maths.** All sums, percentages and trends are computed in Python. The LLM
   receives finished numbers and only (a) assigns unfamiliar merchants to a fixed list of categories,
   (b) writes insights.
4. **Money is never a float.** `Decimal` when parsing, `INTEGER` grosze (`amount_minor`) in the database.
5. **Users are separate.** Each has their own token, transactions, budgets and report. There is no
   shared budget.

---

## 2. Components

| Component | Technology | Where |
| --- | --- | --- |
| Push capture | iOS Shortcuts (automation on IKO notification) | iPhone |
| Inbound buffer | Supabase (Postgres + PostgREST), one table | cloud, free tier |
| CLI / backend | Python 3.14, uv, `argparse`, `httpx`, `pydantic`, `jinja2` | PC |
| Storage | SQLite (stdlib `sqlite3`, no ORM) | PC |
| LLM | Ollama, `gpt-oss:20b` over HTTP `localhost:11434` | PC |
| Report | single HTML: Jinja2 + inline CSS/JS + Chart.js (embedded in the file) | PC → browser |

**Not present and not needed:** a public web server, ORM, Docker, queues, cloud LLMs, Open Banking APIs.
(The local app in §11 listens on 127.0.0.1 only.)

---

## 3. Supabase — inbound buffer

### Table

```sql
create table public.notifications (
  id                bigint generated always as identity primary key,
  created_at        timestamptz not null default now(),
  token_id          text not null,
  notification_text text not null
);
alter table public.notifications enable row level security;

-- The Shortcut uses the publishable/anon key: it can ONLY insert.
create policy "insert only" on public.notifications
  for insert to anon with check (length(notification_text) < 4000 and length(token_id) < 100);
-- No select/update/delete policies for anon → only the secret key (local CLI) can read and delete.
```

### Shortcut contract

```http
POST https://<project>.supabase.co/rest/v1/notifications
apikey: <PUBLISHABLE_KEY>
Content-Type: application/json
Prefer: return=minimal

{"token_id": "<user token>", "notification_text": "<full push text>"}
```

`created_at` is set by the server. The secret/service_role key **never** goes into the Shortcut — with
it, a stolen phone can read and delete everything.

### `pkostat sync`

1. `GET /rest/v1/notifications?order=id.asc&limit=500`, paginated (PostgREST caps responses at ~1000 rows).
2. In one local transaction: `INSERT OR IGNORE` into `raw_notifications` by `remote_id`.
   Rows with an unknown `token_id` → `rejected_notifications` (not lost, but not analysed).
3. **Only after `COMMIT`** — `DELETE ...?id=in.(...)` for the stored ids.
4. A failure between steps 2 and 3 is safe: on the next sync the same `remote_id`s are ignored.

**Two layers of deduplication.**

- *Sync* stores by `remote_id`: re-running `sync` never duplicates rows. Raw input keeps every row
  Supabase had, including copies.
- *Rebuild* drops re-sent copies of one push (e.g. the Shortcut fired twice → two Supabase rows): pushes
  whose whitespace-normalised text is identical count once — **but only when the text pins the event
  down**: card pushes carry `Date:` to the second, account pushes the `Available balance:` after the
  operation (two real 50 zł transfers leave different balances). A text with neither keeps every copy,
  since identical undated texts may be two real purchases.

### Risks

- **Free-tier project pausing** on inactivity — check whether inserts count as activity. While the
  project is paused, pushes are lost (the Shortcut does not retry). CSV import fills that gap
  retroactively.
- **Insert spam** if the publishable key leaks — low risk; junk ends up in `rejected_notifications`.
  Hardening for later: store token hashes in Supabase and check them in `with check`.

---

## 4. Users and tokens

Tokens are generated and stored by the local CLI; Supabase knows nothing about users.

```text
pkostat user add <name>                 # generates a token (secrets.token_urlsafe(24)), prints it
pkostat user add <name> --token <uuid>  # register an existing token (the current UUID)
pkostat user list
pkostat user rotate <name>              # new token; the old one is no longer accepted by sync
pkostat user display-name <name> "Jane Doe"   # name shown in reports ("" clears it)
```

`name` is a technical id (lowercase, used in commands and report paths); `display_name` is free text
for report headers and falls back to `name`.

A token is not a password to the data but a **routing tag**: it tells `sync` whose notification this is.
It is stored in `users.token` in plain text (the local database holds all the data anyway).

---

## 5. Data sources

### 5.1 IKO push notifications (app language — English)

Known formats (examples in `docs/examples/notifications/`):

| Header | What it is | Fields |
| --- | --- | --- |
| `Payment card authorization` | card **hold** (not the final charge) | `Amount`, `Place: <merchant>, <city>`, `Date` with seconds, `Card no.` |
| `Account debit` | account debit (transfer, BLIK phone transfer) | signed amount + type, `Receiver`, `Title`, `Available balance` |
| `Account credit` | incoming money | amount + type, `Sender`, `Title`, `Available balance`; **no date** |

Parsing rules:

- One parser per type: a regex with named groups → `ParsedNotification`. Unrecognised type → no
  transaction is produced; a raw notification without a `transactions` row counts as unparsed, and the
  report shows "N notifications not parsed".
- Transaction date: the `Date` field if present; otherwise `created_at` from Supabase (Europe/Warsaw).
  Pushes can reach Supabase a day or more late (seen on real data), so for `Account debit/credit`,
  which carry no date, the day may be off until a statement supersedes the push.
- Amounts: `"1 943,75"` → `Decimal("1943.75")` → `194375` grosze.
- If the IKO language switches to Polish, the texts change; that is a new set of parsers, not an edit
  of the old ones.

### 5.2 iPKO CSV statement

Example: `docs/examples/fin-audit-html/Zestawienie operacji za ….csv` (1609 rows over 10.5 months).

- Encoding **cp1250**, delimiter `,`, everything quoted.
- Columns: `Data operacji, Data waluty, Typ transakcji, Kwota, Waluta, Saldo po transakcji, Opis transakcji`
  + up to 6 unnamed columns. Columns 7–13 are `Key: value` pairs (`Tytuł`, `Lokalizacja: Adres: … Miasto: … Kraj: …`,
  `Nazwa odbiorcy`, `Nazwa nadawcy`, `Rachunek …`, `Data wykonania operacji`, `Numer karty` …) — parsed into a dict.
- Types (by frequency): `Płatność kartą` 1285, `Płatność web - kod mobilny` (BLIK) 111,
  `Przelew na telefon przychodz. wew./zew.` 112, `Przelew z rachunku` 44, `Zwrot płatności kartą` 18,
  `Przelew na konto` 13, `Zwrot w terminalu` 13, `Blokada` 10, ATM/cash — a handful.
- **`Blokada`** (`Saldo` = `W rozliczeniu`, empty `Data operacji`) — a hold: the money is already
  taken, the booking follows. **Imported and counted** as `pending` (date from `Data waluty`; kind
  `card` when there is a `Lokalizacja`/`Numer karty`, else `other`). In a later statement it appears
  as a settled row and the hold becomes `superseded` (§6).
- Transaction date: `Data wykonania operacji` (actual purchase date, sometimes with `HH:MM`),
  otherwise `Data operacji`.
- **Direction comes from the sign, never from the type name**: PKO labels outgoing phone transfers
  `Przelew na telefon przychodz.` ("incoming") as well — 68 such rows have a negative amount.
- Kind from `Typ transakcji` (stems, since Polish inflects: `w bankomacie`): `zwrot` → refund;
  `bankoma`/`wpłatoma`/`atm` → atm; `kartą` → card; `kod mobilny`/`blik` → blik; `przelew` →
  transfer in/out by sign; anything else → other.
- Refunds (`Zwrot …`) are not income but a reduction of the corresponding merchant's/category's spend.

Import: `pkostat import-csv <file> --user <name>`.

- The whole file → `csv_imports` (file sha256, period `from–to` from the name/dates). Every row is
  parsed first; one broken row rejects the file and nothing is written.
- Importing the same file again is allowed and adds only rows not stored yet (useful after a parser
  change, e.g. when holds started being imported). The same file for a different user is refused.
- Each row → `csv_rows` (raw fields + `row_key`). `row_key` = hash of normalised fields
  `Data operacji|Data waluty|Typ|Kwota|Saldo po transakcji|Opis…`. `Saldo po transakcji` makes the key
  practically unique, so **overlapping statements** (01.01–12.11 and 01.11–30.11) do not duplicate rows.

---

## 6. Reconciling notifications and CSV

One purchase can show up three times: a push at the moment of payment, a `Blokada` row in a
statement exported before the booking, and a settled `Płatność kartą` row in a later statement.
**Precedence: settled row > hold > push.** Lower-ranked copies are marked `superseded`.

Algorithm (on every `import-csv` and `rebuild`, per user):

1. `covered_until` = the latest `period_to` across the user's imports.
2. Holds are reconciled against settled rows; then pushes against settled rows plus the holds still
   pending. The same matching rule applies to both:
3. Two passes, exact first for every record, so a near pair never steals an exact one:
   - *exact*: same amount and currency, date ±3 days, not already used; prefer the same kind, then
     the closest date;
   - *similar* (only what the exact pass left): both card payments, same `merchant_key` (§8),
     date ±1 day, amount within 10 %. Card holds get adjusted before booking — real case: Wolt
     push 273,15, statement hold 268,33.

   Records dated after `covered_until` are not matched.
4. Match found → `status = 'superseded'` + link to the matched CSV row.
5. No match and the date is older than `covered_until − 5 days` → `status = 'unmatched'` (a cancelled
   hold, a parsing error, or someone else's card), shown in the report, not counted.
6. Otherwise `status = 'pending'`: counted, and the report marks it "not booked yet".

Statistics are computed only over `settled` + `pending`.

---

## 7. Data model (SQLite)

The schema is versioned: `src/pkostat/db/migrations/NNN_*.sql` + `PRAGMA user_version`. Tables are
`STRICT`. The sketch below is abridged; the source of truth is `001_initial.sql` and later migrations.

```sql
users(id INTEGER PK, name TEXT UNIQUE, token TEXT UNIQUE, created_at TEXT, display_name TEXT NULL)

raw_notifications(id PK, user_id FK, remote_id INTEGER UNIQUE, received_at TEXT, text TEXT)
rejected_notifications(id PK, remote_id INTEGER UNIQUE, token_id TEXT, received_at TEXT, text TEXT)

csv_imports(id PK, user_id FK, file_name TEXT, file_sha256 TEXT UNIQUE, period_from TEXT,
            period_to TEXT, imported_at TEXT)
csv_rows(id PK, import_id FK, user_id FK, row_key TEXT, raw_json TEXT, UNIQUE(user_id, row_key))

-- Derived table: can be dropped and rebuilt with the rebuild command.
transactions(
  id PK, user_id FK,
  source TEXT,            -- notification | csv
  source_id INTEGER,      -- raw_notifications.id | csv_rows.id
  occurred_on TEXT,       -- YYYY-MM-DD
  occurred_at TEXT NULL,  -- time, if known (push only)
  amount_minor INTEGER,   -- grosze, signed: spend < 0
  currency TEXT,
  kind TEXT,              -- card | blik | transfer_out | transfer_in | refund | atm | other
  counterparty TEXT,      -- merchant or payee/payer name as the bank shows it
  location TEXT,          -- city/country from push "Place" or CSV "Miasto"
  merchant_key TEXT,      -- normalised: 'WOLT', 'BOLT', 'ZABKA', 'ALLEGRO' …
  title TEXT,
  status TEXT,            -- settled | pending | superseded | unmatched
  matched_csv_row_id INTEGER NULL,
  UNIQUE(source, source_id)
)

merchant_rules(merchant_key TEXT PK, category TEXT, source TEXT, updated_at TEXT)  -- manual | llm
transaction_overrides(transaction_source TEXT, source_id INTEGER, category TEXT,
                      PRIMARY KEY(transaction_source, source_id))
reports(id PK, user_id FK, period TEXT, generated_at TEXT, path TEXT, insights_json TEXT)
```

Overrides reference the **raw input** (`source`, `source_id`), not `transactions.id` — otherwise
`rebuild` would lose them.

---

## 8. Categorisation

Two user-editable files in `PKOSTAT_HOME`, created by `pkostat init` from packaged defaults
(`src/pkostat/categorize/defaults/`); without them the defaults are used. Both are validated on load:
unknown kind, unknown category, duplicate name, bad regex or a typo in a key is a clear error.

- `categories.toml` — `[[category]]` with `name`, `kind`, `description`. Kinds: `essential`,
  `discretionary`, `impulse` (spending), `income`, `transfer` (people, cash), `other`. The kind is the
  user's judgement, not the LLM's; the description is what the LLM reads in stage 6.
- `rules.toml` — regexes (case-insensitive, first match wins, optional `kinds` filter):
  `[defaults]` category by operation kind (ATM, transfer in/out); `[[title]]` by transfer title
  (`Wynagrodzenie` → Salary); `[[merchant]]` by counterparty, with an optional `key` that merges
  spellings and an optional `category`.

**Merchant key** (`categorize/merchants.py`): a `[[merchant]]` rule's `key` if one matches
(`WOLT`/`Wolt` → `WOLT`, `PayPro SA *ALLEGRO`/`allegro.pl` → `ALLEGRO`), else a generic clean-up:
upper case, no URL decoration or domain suffix, no tokens containing digits (`ZABKA Z8828 K.1` →
`ZABKA`, `820 IDREAM` → `IDREAM`). Set before reconciliation, which compares merchants (§6).

**Category, first match wins** (`categorize/categorizer.py`):

1. `transaction_overrides` — one operation, keyed by raw input (`source`, `source_id`).
2. `merchant_rules` `manual` — `pkostat category set "<merchant>" "<category>"`.
3. `[[title]]` rules.
4. `[[merchant]]` rules with a category.
5. `[defaults]` by kind — so transfers to unknown people never reach the LLM.
6. `merchant_rules` `llm` — cached LLM answers (stage 6).
7. Nothing → uncategorised; `pkostat uncategorized` lists them by money.

Refunds go through the same chain, so a Wolt refund lowers Food delivery.

**Merchants with two usual categories.** A `[[merchant]]` rule may name an `alternative`
(Wolt: `Food delivery`, alternative `Groceries` — Wolt Market orders look exactly like food in the
bank data: same name, city, title format; amounts overlap; Allegro: `Household & pets`,
alternative `Online marketplaces` — mostly planned bulk buys, sometimes impulse). The Transactions page shows a one-tap
switch on such operations; it stores a `transaction_overrides` row. When the statement supersedes
a push or a hold, rebuild moves its override to the replacing row (`Categorizer.inherit_override`),
so a choice made on the day of the purchase survives the statement. A stored rule or override
naming a category that no longer exists is ignored. Rules are global, not per user.

On the real export the packaged rules categorise ~90 % of transactions; the remainder is small local
shops and services — the LLM's job (stage 6), once per merchant, never per transaction.

---

## 9. Analytics (no LLM)

The `analytics` module takes a list of transactions and returns `Stats` (pydantic), which feeds both
the report and the LLM input. Minimum set:

- Per month: income, spend, net, **savings rate** `(income − spend) / income`.
- Spend by category and by `kind` (essential / discretionary / impulse); change vs the previous month
  and vs the 3-month average.
- Top merchants by amount and by count; average ticket; "how many times a week".
- **Small frequent purchases** (< 30 zł): monthly total — the spending you don't notice.
- **Recurring payments / subscriptions**: same merchant, similar amount, ~30-day interval.
- Outliers: transactions > 3σ above the category's usual ticket.
- P2P: incoming and outgoing totals per person.
- Time of day / day of week — from pushes only (the CSV has no time).
- Budgets (if configured): actual vs limit, end-of-month forecast at the current pace.
- "What if": how much you'd save by cutting category X by N % (for the recommendations block).

---

## 10. LLM (Ollama) — suggestions only

What the local model does after it was measured on real data (roadmap, stage 6): it **suggests**
categories for merchants no rule knows. Nothing it says enters the data unless the owner saves it.

- Client `llm/ollama.py`: `POST /api/chat`, `stream: false`, JSON schema in `format`
  (`model_validate_json`), `num_ctx` 16 384, `temperature` 0, `think` low/medium, one retry on an
  answer that does not fit the schema, readable errors (not running, model missing, GPU crash).
- Suggestions `llm/merchants.py`: batches of 25 unknown merchants (key, spellings, cities,
  operation kinds, payments, typical amount); the category is constrained by the schema to the
  owner's spending categories; the prompt carries the category descriptions and up to 60 of the
  owner's own merchant → category choices as examples; `think: medium`. Answers go to
  `llm_suggestions(merchant_key, category, confidence, model, created_at)`.
- The Uncategorised page pre-selects suggestions with confidence ≥ 0.6 (not "Other") and shows
  every suggestion's confidence; saving turns the choice into a manual merchant rule.
- Measured: 64 % right on 135 known merchants; one confident answer in five wrong. That is why it
  is a suggestion. Known chains are covered by `rules.toml` and never reach the model; what does
  reach it is mostly small local businesses, where neither the model nor a web search knows much.
- The month summary and recommendations are **not** written by the LLM (§11, `analytics/story.py`).
  The first design (model writes the summary from aggregates, numbers checked afterwards) produced
  confident nonsense on real data and was removed.

---

## 11. Local app and report

Day-to-day use is a **local website**: `uv run pkostat` starts a server on `127.0.0.1` and opens the
browser. The CLI stays for automation (Task Scheduler) and development. Nothing about the data flow
changes: the database is still local, the cloud still sees only the push buffer.

- **Stack:** FastAPI + uvicorn serving the report template (`pkostat/report`) in admin mode; edits
  (change a category, upload a CSV, press Sync) go through a small JSON API called with `fetch` —
  no React, no htmx, no build step. Charts are hand-written SVG; CSS and JS live in the package and
  are inlined into the page, which loads nothing from the internet.
- **Numbers vs drawing:** `pkostat.analytics.build_report_data` computes every month at once into
  `ReportData` (pydantic, money in grosze); the page's JS only formats and draws it and switches
  months without a server. The LLM (stage 6) gets the same `ReportData`.
- **Language:** the UI is in Russian; bank data (merchant names, titles, notification texts) is shown
  as received. Categories keep a stable English `name` (rules and stored choices reference it) and get
  a Russian `label` for display.
- **Two audiences:**
  - *Admin* — the local app, used only by the owner of the PC: Report · Transactions (category of one
    operation → override, of the merchant → rule) · Uncategorised · Categories · Data (CSV upload,
    Sync, publish) · Users (add, token, display name, share link). A user switcher picks whose data
    is shown.
  - *User* — a **read-only, self-contained HTML per user**: Report + Transactions (filters, no
    editing), only that user's data embedded. No users, categories, import or sync. This is what
    stage 9 publishes; the other person never touches the local app.
- **Rent attribution:** a category may set `month_shift_from_day` in `categories.toml`; operations
  on or after that day count towards the next month (`Rent & utilities` = 25). Otherwise a month that paid two rents looks broke and
  the next looks rich (real case: October's rent paid on 30.09).
- **Transfers to people** are not spending: shown separately and included in the net (§9).
- **Safety:** bound to `127.0.0.1` only. A website open in the same browser could still send requests
  to localhost, so every request must carry `Host: 127.0.0.1:<port>`/`localhost` (blocks DNS
  rebinding) and changing requests must be POST with a matching `Origin` (blocks cross-site forms).
- **Handlers are thin:** they call the same modules as the CLI (`statement_import`, `sync`,
  `rebuild`, categoriser). No logic lives in the web layer.

**The report** is one page of the app, built from a fixed Jinja2 template (`autoescape=True`) that is
designed once as a mockup and reviewed by the user. The code fills it with `Stats`; the LLM fills only
nothing: the summary and recommendations are built by code (`analytics/story.py`,
`analytics/advice.py`) from the same numbers. Sections (inspired by
`docs/examples/fin-audit-html/financial_audit_2026.html`): verdict for the period (income, spend, net,
savings rate, vs last month) → where the money went (donut of top categories) and the
essential/discretionary/impulse split → leaks → wins → category comparison table (this month, last
month, 3-month average, payments, average ticket; rows expand to merchants) → categories × months
heatmap → spending by kind and income per month → net per month → spending pace within the month →
impulse spending by weekday → top merchants → subscriptions → recommendations → "what if" calculator →
year to date → budgets and goal (if configured) → data notes (statement/push coverage, pending holds,
unmatched, unparsed). Reference mockup: `PKOSTAT_HOME/mockups/` (built on real data, not in git). The same template can be exported as one self-contained
HTML file (archive, stage 9 cloud publishing). LLM text is inserted only as escaped text.

---

## 12. Budgets and goals (optional)

Edited in the app ("Бюджеты" page) and stored per user in the database: `goals(user_id,
monthly_saving)` and `budgets(user_id, category, month_limit)`, grosze. No goal and no limits =
the block is hidden. Computed in `analytics/budgets.py` for every month:

- limit lines: spent, limit, status `ok` / `near` (≥ 85 % or forecast above the limit) / `over`;
  for the running month a forecast = spent ÷ days with data × days in month (categories with a
  month shift, i.e. rent, are paid once: forecast = spent);
- goal: complete month → met if net ≥ goal; running month → left to spend = expected income
  (the larger of income so far and the 3-month average, since salary lands at the month's end)
  − goal − spent + transfers, and per remaining day.

The original plan was a hand-edited `budgets.toml` (superseded, kept for history):

```toml
[user.jane]
monthly_saving = 2000          # goal: amount to save per month, zł

[user.jane.limits]       # per-category limits, zł/month (names from categories.toml)
"Food delivery" = 800
"Taxi" = 250
```

`pkostat report` reads the file if present; no file or no section for the user → the budgets block is
not rendered and the LLM receives no limit data.

---

## 13. Configuration and files

```text
~/pkostatistics/                   (PKOSTAT_HOME)
├── .env                           SUPABASE_URL, SUPABASE_SECRET_KEY, OLLAMA_URL, OLLAMA_MODEL
├── db/pkostat.db
├── categories.toml                category list and their kind (created by `init`, user-edited)
├── rules.toml                     merchant keys and category rules (created by `init`, user-edited)
├── budgets.toml                   optional
├── reports/<user>/*.html
└── backups/pkostat-YYYY-MM-DD.db  pkostat backup (sqlite backup API)
```

User data **does not live in the repository**. The repository contains only code, default
`categories.toml`/prompts and **anonymised** test fixtures.

After `sync` a notification exists only locally → **backups are mandatory** (`backup.py`): a zip
with a consistent SQLite snapshot (backup API, safe while the app runs) plus `categories.toml`
and `rules.toml` — never `.env`, since the folder may be a cloud drive. Made by `pkostat backup`,
at the end of every `pkostat run`, and once a day when the app starts; the 30 newest are kept;
`PKOSTAT_BACKUP_DIR` moves them (e.g. to OneDrive). `pkostat restore FILE` checks integrity and
schema version, saves the current state as one more backup, then replaces the database and the
TOML files (the app must be closed).

---

## 14. CLI

```text
pkostat                            = pkostat serve: the local admin website on 127.0.0.1:8765
pkostat user add|list|rotate|display-name   users, tokens, report names
pkostat sync                       Supabase → raw_notifications → delete from Supabase
pkostat import-csv FILE --user U   iPKO statement
pkostat rebuild [--user U]         rebuild transactions from raw input (parsing + reconciliation)
pkostat category list|set|unset    categories; per-merchant rules
pkostat uncategorized [--user U]   merchants without a category, by money
pkostat categorize [--user U]      LLM for unknown merchants (stage 6)
pkostat report --user U [--open]   read-only report HTML (PKOSTAT_HOME/reports/<user>/report.html)
pkostat run [--no-llm]             sync → rebuild → LLM merchants → LLM texts → reports → backup
pkostat backup [--list]            zip of the database and TOML files
pkostat restore FILE               restore a backup (app closed)
```

Run with `uv run pkostat …` (entry point in `pyproject.toml`). Optional automation via Windows Task
Scheduler (`pkostat run` once a week).

## 15. Package layout

```text
src/pkostat/
├── cli.py               argparse parser only
├── commands/            handlers (users, data, categories): settings → module call → output
├── config.py            Settings from .env / environment
├── home.py              PKOSTAT_HOME layout, init, opening the database
├── clock.py             Europe/Warsaw time helpers
├── users.py             users and tokens
├── db/                  connection.py, migrate.py, migrations/NNN_*.sql, repositories (SQL only here)
├── ingest/              supabase.py (inbox client), sync.py, notifications/ (parsers),
│                        statement/ (reader.py: file → raw rows; parser.py: row → entry)
├── statement_import.py  import-csv: validate every row, then store the file and its rows
├── reconcile.py         push ↔ CSV reconciliation
├── rebuild.py           transactions = parsed statement rows + parsed, reconciled pushes
├── categorize/          config.py (TOML), merchants.py (keys), categorizer.py, defaults/*.toml
├── analytics/           months.py (placing, totals), findings.py (comparison, leaks/wins, share),
│                        patterns.py (pace, weekdays, recurring), overview.py (year to date,
│                        what if), report_data.py (assembly), model.py (ReportData)
├── llm/                 ollama.py (client), prompts/*.md, schemas.py
├── report/              render.py, templates/report.html.j2, static/report.css, static/js/*.js
│                        (both modes), static/admin/*.js (admin mode only, never published)
└── web/                 app.py, guard.py (Host/Origin checks), context.py, pages.py (admin
                         payload), routes_data.py (categories, upload, sync), routes_admin.py
tests/
├── fixtures/            anonymised notifications and CSV snippets
└── test_*.py
```

---

## 16. Later: report in the cloud (stage 9)

What is published: the *user* HTML of §11, one per user, served at a secret URL such as
`/r/<share-id>` (Cloudflare Pages or Workers static assets).

- **`share_id` is not the push token.** The token lets anyone insert pushes for that user; it lives
  in the iOS Shortcut and must not appear in a URL. Each user gets a separate random `share_id`
  (≥ 128 bits), stored locally, rotatable from the Users page (rotation = old link stops working).
- The link is the access: whoever has it sees the report. Acceptable for two people; if not, put
  Cloudflare Access (email-code login) in front — no auth code on our side.
- Publishing replaces the file at the same URL; nothing else is uploaded. The cloud never receives
  the database.

---

## 17. Open questions

- Is a push sent for online BLIK payments (`Płatność web - kod mobilny`, 111 transactions in the CSV),
  refunds, ATM withdrawals, standing orders? Sample texts needed.
- What does a push look like for a foreign-currency payment (amount in EUR + exchange rate)?
- Does the Supabase free project get paused despite daily inserts?
- Does the user have other accounts / a savings account: transfers to them are savings, not spend.

---

## 18. Decision log

| Date | Question | Decision | Why |
| --- | --- | --- | --- |
| 2026-11-18 | Where to store data | Local SQLite; Supabase is only a push buffer | Bank data stays out of the cloud, no free-tier limits, simpler |
| 2026-11-18 | Cloudflare Workers + D1 (previous version of this doc) | Rejected | No server needed: Supabase handles push intake, the rest is local |
| 2026-11-18 | Who generates tokens | The local CLI | Supabase doesn't need to know users; a token is a routing tag |
| 2026-11-18 | Second user | Fully separate data and reports | User requirement |
| 2026-11-18 | Report | Local HTML; cloud publishing is a separate later stage | Value first, infrastructure later |
| 2026-11-18 | Budgets and goals | Optional `budgets.toml` | Needed to "start saving", but not mandatory |
| 2026-11-18 | Who computes numbers | Python only; the LLM does categories and text | LLMs get arithmetic wrong; numbers must be reproducible |
| 2026-11-18 | Categorisation | LLM per merchant, cached in `merchant_rules`, manual rules take priority | Stable between runs, few calls |
| 2026-11-18 | Money | `Decimal` → `INTEGER` grosze | Floats accumulate rounding errors |
| 2026-11-18 | Push deduplication | By Supabase `id`, not by text | Identical text ≠ the same transaction |
| 2026-11-18 | Push vs CSV | CSV is the truth; pushes are matched and marked `superseded` | Pushes are holds; the statement has final charges |
| 2026-11-18 | Parse status on raw notifications | Not stored; unparsed = raw row without a transaction | Raw input stays immutable |
| 2026-11-18 | `.env` loading | `python-dotenv` | Standard, no hand-rolled parser |
| 2026-11-18 | Time zones on Windows | `tzdata` dependency | Windows has no system tz database; `zoneinfo` needs it |
| 2026-11-18 | Transfer direction in CSV | By amount sign | `Przelew na telefon przychodz.` is used for outgoing transfers too |
| 2026-11-18 | Broken row in a statement | Reject the whole file, write nothing | No half-imported statements |
| 2026-11-18 | Re-sent pushes (Shortcut fired twice) | Dropped in rebuild when text has `Date:` or `Available balance:` | Those make identical text = same event; raw rows are kept |
| 2026-11-18 | Statement holds (`Blokada`) | Import and count as pending; superseded by the booked row later (reverses "not imported") | The money is already gone; holds are rarely cancelled |
| 2026-11-18 | Re-importing the same file | Allowed, adds only missing rows (reverses "rejected") | Rows are deduplicated by content anyway; lets a parser change reach old files |
| 2026-11-18 | Hold amount differs from the push | Second "similar" pass: card, same merchant, ±1 day, ≤10 % | Wolt adjusts holds; exact-only matching double-counted an order |
| 2026-11-18 | Where categories and rules live | `categories.toml` + `rules.toml` in PKOSTAT_HOME (copied from packaged defaults), per-merchant choices in `merchant_rules` | Files for bulk editing, a command for one-off choices |
| 2026-11-18 | Transfers to unknown people | Category by kind default, never sent to the LLM | The LLM cannot know who a person is |
| 2026-11-18 | Report HTML | Fixed Jinja2 template reviewed as a mockup first; the LLM fills text slots only | Same look every run; the LLM must not invent layout or numbers |
| 2026-11-18 | ORM / web framework / CLI framework | None: `sqlite3`, `argparse` | 1–2 users, minimal dependencies |
| 2026-11-18 | UI language | Russian UI, report and LLM insights; bank data as received; code/CLI in English (reverses "all user-facing text in English" for the UI) | Owner's preference; merchant names must match the bank |
| 2026-11-18 | Who can change what | Admin = local app only; other users get a read-only published HTML with only their data | Nobody else can add users or change categories |
| 2026-11-18 | Published report URL | Separate random `share_id`, never the push token | The token authorises inserting pushes |
| 2026-11-18 | Rent paid at month end | Rent paid on the 25th or later belongs to the next month | Otherwise months alternate between "broke" and "rich" |
| 2026-11-18 | Transfers to people | Not spending; shown separately, counted in net | Confirmed by the owner: personal transfers, not shared expenses |
| 2026-11-18 | Where report numbers are computed | Python (`analytics`) for every month at once; JS only draws | Testable, identical for the page and the LLM, works offline in the published file |
| 2026-11-18 | htmx | Not used; plain `fetch` to a JSON API (amends the local-app decision) | The mockup's interactivity is already plain JS; one less vendored library |
| 2026-11-18 | LLM recommendations | Category + plan chosen by the model, saving computed by code; change directions given as words | Free-form output misread directions and quoted wrong amounts on real data |
| 2026-11-18 | LLM merchant answers | Stored as `llm` rules only with confidence ≥ 0.6 and not "Other"; manual rules always win | The model is confidently wrong sometimes (fuel station → groceries) |
| 2026-11-18 | Where budgets live | Database per user, edited in the app (supersedes `budgets.toml`) | Everything else is edited in the app; per-user data belongs with the user |
| 2026-11-18 | Default user in the app | First user created, not first by name | The owner adds others later; their names may sort first |
| 2026-11-18 | Backups | Zip of a SQLite snapshot + TOML files, no `.env`, 30 kept, daily on app start | Pushes exist only locally after sync; the backup folder may be in a cloud |
| 2026-11-18 | `pkostat run` failures | Each step isolated; report and backup still run; exit code 1 | A missing Ollama or network must not cost the backup |
| 2026-11-18 | LLM merchant answers | Suggestions the owner confirms; never applied alone (reverses "stored as llm rules") | Blind test: 64 % right, 1 in 5 confident answers wrong |
| 2026-11-18 | Month summary and advice | Built by code from computed numbers; LLM texts removed (reverses "category + plan chosen by the model") | All 11 real months reviewed: wrong directions, contradicting advice; every fact was already computed |
| 2026-11-18 | Baseline for comparisons | Only months inside the report range | A stray December booking made January "+2554 %" |
| 2026-11-19 | Wolt food vs groceries | Per-operation switch from an `alternative` category; overrides carried from push/hold to the statement row | Indistinguishable in bank data; a Wolt order history import stays an option |
| 2026-11-19 | Allegro | `Household & pets` (essential) by default, `Online marketplaces` as the switch | Owner: mostly planned bulk buys (pet food, litter, chemicals); impulse buys are the exception |
| 2026-11-19 | Month the report opens on | The latest month, running or not (was: last complete month) | Limits, forecast and "left to spend" are about the running month |
| 2026-11-19 | Sharing with the second user (iPhone) | A published link (stage 9), not an HTML file or PDF | iOS previews attachments with JavaScript off: the report would be blank; PDF loses interactivity |
| 2026-11-18 | Everyday interface | Local website (FastAPI + Jinja2 + htmx on 127.0.0.1), built together with the report; CLI kept for automation (reverses "no web server" for the local side) | Typing `category set` per merchant is unusable; a browser UI needs no extra install |
