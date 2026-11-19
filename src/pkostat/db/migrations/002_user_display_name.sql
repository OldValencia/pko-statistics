-- Human-readable name for reports; NULL means "use users.name".
ALTER TABLE users ADD COLUMN display_name TEXT;
