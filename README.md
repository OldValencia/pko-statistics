# PkoStat

A personal spending analyser for a PKO BP account. IKO push notifications (sent from the iPhone to a
Supabase buffer) and iPKO CSV statements are collected into a **local** SQLite database. The app
reconciles them, sorts spending into categories and shows a report with limits, a saving goal and
advice. A local LLM (Ollama) only suggests categories for unknown merchants.

Everything except the Supabase buffer stays on this PC.

## Requirements

- Windows 11 (other systems should work, the `.bat` launchers are Windows-only)
- [uv](https://docs.astral.sh/uv/) — installs Python 3.14 and the dependencies itself
- Optional: [Ollama](https://ollama.com/) with `gpt-oss:20b` for category suggestions
- A Supabase project (free tier is enough) for push notifications
- An iPhone with IKO and the Shortcuts app

## Where things live

| What | Where |
| --- | --- |
| Code | this repository |
| Data folder (`PKOSTAT_HOME`) | `~/pkostatistics` by default (`C:\Users\<you>\pkostatistics`) |
| Settings and secrets | `~/pkostatistics/.env` |
| Database | `~/pkostatistics/db/pkostat.db` |
| Categories and rules | `~/pkostatistics/categories.toml`, `~/pkostatistics/rules.toml` |
| Reports | `~/pkostatistics/reports/<user>/report.html` |
| Backups | `~/pkostatistics/backups/` or `PKOSTAT_BACKUP_DIR` |

The data folder is not in git and must never be. Set the `PKOSTAT_HOME` environment variable to use
another folder.

## First-time setup

### 1. Code and environment

```powershell
git clone git@github.com:OldValencia/pko-statistics.git
cd pko-statistics
uv sync
uv run pkostat init
```

`init` creates the data folder, a `.env` template, `categories.toml`, `rules.toml` and the database.
It never overwrites existing files, so it is safe to run again.

### 2. Supabase

Create a project, then run this in the SQL editor:

```sql
create table public.notifications (
  id                bigint generated always as identity primary key,
  created_at        timestamptz not null default now(),
  token_id          text not null,
  notification_text text not null
);
alter table public.notifications enable row level security;

-- The phone uses the publishable key: it can ONLY insert.
create policy "insert only" on public.notifications
  for insert to anon with check (length(notification_text) < 4000 and length(token_id) < 100);
-- No select/update/delete policies: only the secret key (this PC) can read and delete.
```

Settings → API keys gives two keys:

- **publishable** key — goes into the iPhone Shortcut;
- **secret** key — goes only into `.env` on this PC. Never put it on the phone.

### 3. `.env`

Fill `~/pkostatistics/.env`:

```dotenv
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SECRET_KEY=<secret key>
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
# Optional: keep backups outside the data folder, e.g. in a cloud-synced folder.
PKOSTAT_BACKUP_DIR=
# Optional: publish encrypted read-only reports to GitHub Pages (see "Sharing a report").
PKOSTAT_PUBLISH_REMOTE=git@github.com:<owner>/<repo>.git
# Empty = https://<owner>.github.io/<repo>
PKOSTAT_PUBLISH_URL=
```

Environment variables with the same names override the file.

### 4. Users and tokens

Each person has a token; it tells the app whose notification arrived.

```powershell
uv run pkostat user add jane --display-name "Jane Doe"   # prints a new token
uv run pkostat user add jane --token <existing-token>    # or register a token the phone already uses
uv run pkostat user list
uv run pkostat user rotate jane                           # new token; the old one stops working
uv run pkostat user display-name jane "Jane Doe"
```

Users can also be added on the Users page of the app.

### 5. iPhone Shortcut

An automation that runs on an IKO notification and sends its text:

```http
POST https://<project>.supabase.co/rest/v1/notifications
apikey: <publishable key>
Content-Type: application/json
Prefer: return=minimal

{"token_id": "<user token>", "notification_text": "<full notification text>"}
```

Set the IKO app language to English: the notification parsers expect English texts.

### 6. Ollama (optional)

```powershell
ollama pull gpt-oss:20b
ollama list
```

Without Ollama everything works except the category suggestions.

### 7. First data

Export the statement from iPKO ("Zestawienie operacji", CSV) and import it, or use the Data page:

```powershell
uv run pkostat import-csv path\to\statement.csv --user jane
uv run pkostat sync
```

## Everyday use

```powershell
uv run pkostat            # the app on http://127.0.0.1:8765 (or double-click run.bat)
```

The app imports statements, syncs pushes, edits categories, limits and goals, and makes backups.
"Обновить всё" on the Data page runs the whole pipeline.

### Commands

```text
pkostat [serve] [--port N] [--no-browser]   the local app (default command)
pkostat init                                 create the data folder, .env template, configs, database
pkostat user add|list|rotate|display-name    users and tokens
pkostat user share NAME [--off]              new link to the user's published report
pkostat sync                                 move notifications from Supabase into the database
pkostat import-csv FILE --user U             import an iPKO CSV statement
pkostat rebuild [--user U]                   rebuild transactions from stored raw data
pkostat category list|set|unset              categories and per-merchant rules
pkostat uncategorized [--user U]             merchants without a category
pkostat categorize [--user U]                LLM suggests categories (confirm in the app)
pkostat report --user U [--open]             read-only report HTML
pkostat run [--no-llm]                       sync, rebuild, LLM, reports, publish, backup
pkostat publish [--force]                    push encrypted reports, only if something changed
pkostat backup [--list]                      back up the database and config files
pkostat restore FILE                         restore a backup (close the app first)
```

Prefix each with `uv run`, or use `run.bat <command>`.

### Daily run (optional)

`run-daily.bat` runs `pkostat run` and logs to `~/pkostatistics/logs/run.log`. To schedule it:

```powershell
schtasks /Create /TN "PkoStat daily" /SC DAILY /ST 21:00 /TR "\"D:\Projects\pkostatistics\run-daily.bat\""
```

The PC must be on at that time; Ollama must be running for the LLM step.

## Sharing a report

A user's read-only report can be published as a web page, for example to read it on a phone. It is
published to GitHub Pages of this repository (branch `gh-pages`) and **encrypted on this PC**: the
repository and the site are public, the page is not readable without the password.

1. Set `PKOSTAT_PUBLISH_REMOTE` in `.env` (the repository to push `gh-pages` to; this PC's SSH key
   must be able to push there) and restart the app.
2. Users page → "Открыть доступ" for the user. This creates a random address and password and
   publishes. Or: `uv run pkostat user share jane` then `uv run pkostat publish`.
3. The first time, check the repository's Settings → Pages: source "Deploy from a branch",
   `gh-pages`, `/ (root)`.
4. "Копировать ссылку" and send it. The password is in the link after `#`: browsers never send that
   part to the server. The phone remembers it after the first opening.

"Новая ссылка" replaces the address and password (the old link stops working); "Закрыть" removes
the page. Each publish replaces the whole `gh-pages` branch with one commit.

To keep the page fresh every 2 hours (sync, rebuild, publish only if changed; log in
`~/pkostatistics/logs/publish.log`):

```powershell
schtasks /Create /TN "PkoStat publish" /SC HOURLY /MO 2 /TR "\"D:\Projects\pkostatistics\run-publish.bat\""
```

## Backups and recovery

A backup is a zip with a consistent copy of the database plus `categories.toml` and `rules.toml`.
It is made by `pkostat backup`, at the end of every `pkostat run`, and once a day when the app starts;
it also holds the users' share links and passwords, so restored links keep working.
the 30 newest are kept. **`.env` is never backed up** — keep the Supabase URL and secret key in a
password manager.

Set `PKOSTAT_BACKUP_DIR` to a folder outside `~/pkostatistics` (a cloud-synced folder works).
Otherwise deleting the data folder deletes the backups too.

### If the data folder was deleted

1. Recreate the folder:

   ```powershell
   uv run pkostat init
   ```

2. Fill `~/pkostatistics/.env` again (step 3 above), including `PKOSTAT_BACKUP_DIR`.

3. Restore the newest backup. Users, tokens, categories, limits and goals come back with it:

   ```powershell
   uv run pkostat backup --list
   uv run pkostat restore <path>\pkostat-YYYY-MM-DD_HHMMSS.zip
   ```

4. Check the result:

   ```powershell
   uv run pkostat user list
   uv run pkostat sync
   uv run pkostat
   ```

### If there is no backup

1. Run `init` and fill `.env` as above.
2. Register users with the tokens the phone already sends, so the Shortcut does not need changes.
   The token is in the Shortcut's request body.

   ```powershell
   uv run pkostat user add jane --token <token from the Shortcut>
   ```

3. Import the CSV statements again. Pushes that were already synced and deleted from Supabase are
   lost, but the statement covers the same operations.
4. Run `uv run pkostat sync`.
5. Set limits, goals and merchant categories again in the app.

## Development

```powershell
uv run ruff format
uv run ruff check --fix
uv run pytest
```

Project notes for contributors (and AI assistants) are in `CLAUDE.md` and `docs/`.
