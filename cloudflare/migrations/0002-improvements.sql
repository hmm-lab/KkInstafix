CREATE TABLE IF NOT EXISTS message_originals (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, original_json TEXT NOT NULL, platform TEXT, provider TEXT, ts INTEGER NOT NULL, PRIMARY KEY(chat_id,bot_msg_id));
CREATE INDEX IF NOT EXISTS idx_message_originals_ts ON message_originals(ts);
CREATE TABLE IF NOT EXISTS provider_health (platform TEXT NOT NULL, provider TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0, cooldown_until INTEGER NOT NULL DEFAULT 0, checked_at INTEGER NOT NULL, last_success_at INTEGER NOT NULL DEFAULT 0, last_status INTEGER, evidence TEXT NOT NULL, PRIMARY KEY(platform,provider));
CREATE TABLE IF NOT EXISTS provider_probe_cursor (id INTEGER PRIMARY KEY CHECK(id=1), cursor INTEGER NOT NULL, slot INTEGER NOT NULL);
