-- LLM summary and recommendations per user and month. input_hash identifies the numbers the text
-- was written from: when the month's numbers change, the text is shown as outdated.
CREATE TABLE insights (
    user_id      INTEGER NOT NULL REFERENCES users (id),
    month        TEXT NOT NULL,
    input_hash   TEXT NOT NULL,
    model        TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    content_json TEXT NOT NULL,
    PRIMARY KEY (user_id, month)
) STRICT;
