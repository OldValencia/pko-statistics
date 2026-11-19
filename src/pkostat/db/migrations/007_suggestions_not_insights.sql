-- The LLM no longer writes month texts (code builds them from the numbers), and its merchant
-- answers are suggestions the owner confirms, never rules applied on their own.
DROP TABLE insights;

CREATE TABLE llm_suggestions (
    merchant_key TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    confidence   REAL NOT NULL,
    model        TEXT NOT NULL,
    created_at   TEXT NOT NULL
) STRICT;
