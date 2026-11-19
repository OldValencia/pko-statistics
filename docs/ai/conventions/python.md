# PkoStat — How to Write Code

Python 3.14, uv, ruff, pytest. The goal is boring, predictable code that reads without context six
months later. Hard rules are in `mandates.md`.

## Structure

- Package `src/pkostat/`, tests in `tests/`. Module layout — architecture §15.
- Absolute imports: `from pkostat.db.repositories import TransactionRepo`. No relative `from ..x`, no
  imports inside functions (except to break a real cycle — with a comment saying why).
- Layers and dependency direction:
  `cli → (ingest | reconcile | categorize | analytics | report) → db`; `llm` is used by `categorize`
  and `report`. `analytics` is pure functions with no I/O: transactions in, `Stats` out.
- `cli.py` only parses arguments and calls functions. No logic in it.

## Types and models

- Type annotations everywhere, including return `-> None`. `list[str]`, `X | None`; no `typing.List`/`Optional`.
- **pydantic** — at the boundaries: JSON from Supabase, LLM responses, `Stats` (serialised to JSON for
  the LLM and the template), TOML configs.
- **`@dataclass(frozen=True, slots=True)`** — internal domain objects (`ParsedNotification`,
  `Transaction`). Immutable; "modify" = `dataclasses.replace`.
- String enumerations stored in the DB (`kind`, `status`, `source`) — `enum.StrEnum`.

## Money, dates, text

- Amount: `Decimal` from a string (`"1 943,75"` → strip spaces/NBSP, `,` → `.`) → `int` grosze.
  The helpers live in one place (`pkostat/money.py`); amounts are parsed nowhere else.
- Dates in the DB are ISO strings: `YYYY-MM-DD` for a day, `YYYY-MM-DDTHH:MM:SS` for a time in
  Europe/Warsaw. Convert `datetime` from Supabase (UTC) to `ZoneInfo("Europe/Warsaw")` before storing.
- Open PKO CSVs with `encoding="cp1250"`, `newline=""`, via `csv.reader`.
- Notification parsers — regexes with named groups, compiled at module level, one module per
  notification type. Unrecognised text → `None`/`unparsed`, not an exception.

## Database

- stdlib `sqlite3`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`.
- Transactions: `with conn:`. External side effects (deleting in Supabase) happen **after** leaving the block.
- Repositories return domain objects; `sqlite3.Row` never leaves `db/`.

## LLM

- One client, `llm/ollama.py`: `chat(messages, schema: type[BaseModel]) -> BaseModel`.
- Prompts are files in `llm/prompts/*.md`, filled via `str.format` or Jinja2. Don't build prompts by
  string concatenation in business logic.
- Explicit timeouts (`httpx.Timeout`); model and URL from `Settings`.

## Errors and output

- Expected user errors (missing file, unknown user, Ollama not running) — a custom `PkoStatError` with a
  clear message in English; `cli` catches it and prints it without a traceback.
- Unexpected errors — don't swallow them. No bare `except:` and no `except Exception: pass`.
- `logging` for diagnostics (`-v` enables DEBUG); `print` only for final command output in `cli`.
- CLI output is plain ASCII where possible: Windows consoles and redirected output may not be UTF-8.
- Code, CLI and logs are in English: identifiers, comments, docstrings, CLI output, error messages,
  LLM prompts.
- The web UI and the report are in **Russian**: labels, headings, verdicts, notes, category labels,
  and the LLM's insights (prompts ask for Russian output). Bank data stays as received: merchant
  names, transfer titles, notification texts are never translated.
- Russian plurals go through one helper (`1 платёж, 2 платежа, 5 платежей`), never `платежей(а)`.
  UI text avoids gendered verb forms about the user ("расходы превысили доход", not "ты потратил").

## Comments

A comment explains **why**, not what: "`Blokada` skipped: becomes `Płatność kartą` in the next
statement", not "skip blokada". No commented-out code and no TODOs without context.

## Tests

- `pytest`, files `tests/test_<module>.py`, fixtures in `tests/fixtures/` (anonymised).
- Must be covered: parsing of each notification type, parsing of each CSV row type, money helpers,
  push ↔ CSV reconciliation, key `analytics` metrics.
- Tests never call the LLM: the client is replaced by a fake returning a ready pydantic model.
- Test database — `sqlite3.connect(":memory:")` with migrations applied.

## Report (HTML)

- Jinja2 with `autoescape=True`. Data goes into the page as `<script type="application/json" id="data">`
  + `JSON.parse`, not by interpolation into JS.
- No external resources: Chart.js and fonts are embedded or system fonts.
- Visual reference — `docs/examples/fin-audit-html/financial_audit_2026.html` (dark theme, KPI cards,
  "leaks", charts, filterable register).
