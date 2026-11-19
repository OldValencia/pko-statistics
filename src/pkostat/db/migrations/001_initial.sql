-- Initial schema. See docs/pko-expenses-architecture.md §7.
-- Money is INTEGER grosze; dates are ISO-8601 TEXT in Europe/Warsaw.

CREATE TABLE users (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    token      TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
) STRICT;

-- Raw input: written once by sync, never updated or deleted.
CREATE TABLE raw_notifications (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id),
    remote_id   INTEGER NOT NULL UNIQUE,
    received_at TEXT NOT NULL,
    text        TEXT NOT NULL
) STRICT;

CREATE TABLE rejected_notifications (
    id          INTEGER PRIMARY KEY,
    remote_id   INTEGER NOT NULL UNIQUE,
    token_id    TEXT NOT NULL,
    received_at TEXT NOT NULL,
    text        TEXT NOT NULL
) STRICT;

CREATE TABLE csv_imports (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id),
    file_name   TEXT NOT NULL,
    file_sha256 TEXT NOT NULL UNIQUE,
    period_from TEXT NOT NULL,
    period_to   TEXT NOT NULL,
    imported_at TEXT NOT NULL
) STRICT;

-- Raw input: one row per statement line, deduplicated across overlapping statements by row_key.
CREATE TABLE csv_rows (
    id        INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES csv_imports (id),
    user_id   INTEGER NOT NULL REFERENCES users (id),
    row_key   TEXT NOT NULL,
    raw_json  TEXT NOT NULL,
    UNIQUE (user_id, row_key)
) STRICT;

-- Derived: dropped and rebuilt from raw input by `pkostat rebuild`.
-- A raw notification with no row here is reported as unparsed.
CREATE TABLE transactions (
    id                 INTEGER PRIMARY KEY,
    user_id            INTEGER NOT NULL REFERENCES users (id),
    source             TEXT NOT NULL CHECK (source IN ('notification', 'csv')),
    source_id          INTEGER NOT NULL,
    occurred_on        TEXT NOT NULL,
    occurred_at        TEXT,
    amount_minor       INTEGER NOT NULL,
    currency           TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (
        kind IN ('card', 'blik', 'transfer_out', 'transfer_in', 'refund', 'atm', 'other')
    ),
    counterparty       TEXT,
    merchant_key       TEXT,
    title              TEXT,
    status             TEXT NOT NULL CHECK (
        status IN ('settled', 'pending', 'superseded', 'unmatched')
    ),
    matched_csv_row_id INTEGER REFERENCES csv_rows (id),
    UNIQUE (source, source_id)
) STRICT;

CREATE INDEX idx_transactions_user_day ON transactions (user_id, occurred_on);
CREATE INDEX idx_transactions_merchant ON transactions (merchant_key);

CREATE TABLE merchant_rules (
    merchant_key TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    source       TEXT NOT NULL CHECK (source IN ('manual', 'llm')),
    updated_at   TEXT NOT NULL
) STRICT;

-- Keyed by raw input, not transactions.id, so overrides survive a rebuild.
CREATE TABLE transaction_overrides (
    transaction_source TEXT NOT NULL CHECK (transaction_source IN ('notification', 'csv')),
    source_id          INTEGER NOT NULL,
    category           TEXT NOT NULL,
    PRIMARY KEY (transaction_source, source_id)
) STRICT;

CREATE TABLE reports (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users (id),
    period        TEXT NOT NULL,
    generated_at  TEXT NOT NULL,
    path          TEXT NOT NULL,
    insights_json TEXT
) STRICT;
