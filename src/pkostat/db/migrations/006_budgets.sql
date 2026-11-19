-- Optional per-user money plan, edited in the app: a monthly saving goal and category limits.
CREATE TABLE goals (
    user_id        INTEGER PRIMARY KEY REFERENCES users (id),
    monthly_saving INTEGER NOT NULL CHECK (monthly_saving > 0)
) STRICT;

CREATE TABLE budgets (
    user_id     INTEGER NOT NULL REFERENCES users (id),
    category    TEXT NOT NULL,
    month_limit INTEGER NOT NULL CHECK (month_limit > 0),
    PRIMARY KEY (user_id, category)
) STRICT;
