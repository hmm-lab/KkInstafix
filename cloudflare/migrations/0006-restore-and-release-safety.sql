CREATE INDEX IF NOT EXISTS idx_user_settings_chat ON user_settings(chat_id);
CREATE TABLE IF NOT EXISTS backup_restore_receipts (update_id INTEGER PRIMARY KEY, reply TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_backup_restore_receipts_ts ON backup_restore_receipts(ts);
CREATE TABLE IF NOT EXISTS release_checks (nonce TEXT PRIMARY KEY, build TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_release_checks_ts ON release_checks(ts);
