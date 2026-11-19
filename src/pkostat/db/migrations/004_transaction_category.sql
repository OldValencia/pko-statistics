-- Category assigned on rebuild (see categorize/categorizer.py); NULL = not categorised yet.
ALTER TABLE transactions ADD COLUMN category TEXT;

CREATE INDEX idx_transactions_category ON transactions (user_id, category);
