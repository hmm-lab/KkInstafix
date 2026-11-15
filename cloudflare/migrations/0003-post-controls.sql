CREATE TABLE IF NOT EXISTS post_controls (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, source_msg_id INTEGER NOT NULL, user_id INTEGER NOT NULL, state_json TEXT NOT NULL, ts INTEGER NOT NULL, lock_until INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(chat_id,bot_msg_id), UNIQUE(chat_id,source_msg_id));
CREATE INDEX IF NOT EXISTS idx_post_controls_ts ON post_controls(ts);
