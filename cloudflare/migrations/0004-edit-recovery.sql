CREATE TABLE IF NOT EXISTS post_operations (operation_id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, desired_json TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_post_operations_message ON post_operations(chat_id,bot_msg_id,state);
CREATE INDEX IF NOT EXISTS idx_post_operations_ts ON post_operations(ts);
CREATE TABLE IF NOT EXISTS post_activity (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, last_action_at INTEGER NOT NULL, PRIMARY KEY(chat_id,bot_msg_id));
