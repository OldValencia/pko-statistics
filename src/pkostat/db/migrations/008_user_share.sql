-- Publishing the read-only report (stage 9): a secret path and the password that encrypts it.
-- Both NULL = the user's report is not published.
ALTER TABLE users ADD COLUMN share_id TEXT;
ALTER TABLE users ADD COLUMN share_password TEXT;
CREATE UNIQUE INDEX users_share_id ON users (share_id);
