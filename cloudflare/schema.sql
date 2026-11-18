
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            sender_mode TEXT NOT NULL DEFAULT 'first_name',
            dedup_window INTEGER NOT NULL DEFAULT 60,
            rate_limit INTEGER NOT NULL DEFAULT 5,
            rate_window INTEGER NOT NULL DEFAULT 30,
            ignore_forwards INTEGER NOT NULL DEFAULT 1,
            provider_fallback INTEGER NOT NULL DEFAULT 1,
            caption_style TEXT NOT NULL DEFAULT 'reply',
            text_spam INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS provider_settings (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            provider TEXT NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS blocked_users (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS disabled_platforms (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS platform_overrides (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS optout_users (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS chat_stats (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            sender_id INTEGER NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0,
            last_ts INTEGER NOT NULL,
            PRIMARY KEY (chat_id, platform, sender_id)
        );

        CREATE TABLE IF NOT EXISTS rewritten_messages (
            chat_id INTEGER NOT NULL,
            bot_msg_id INTEGER NOT NULL,
            original_url TEXT NOT NULL,
            sender_name TEXT,
            ts INTEGER NOT NULL,
            PRIMARY KEY (chat_id, bot_msg_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rewritten_ts ON rewritten_messages(ts);

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, chat_id, key)
        );
        
CREATE TABLE IF NOT EXISTS runtime_config (id INTEGER PRIMARY KEY CHECK(id=1), token_cipher TEXT NOT NULL, bot_id INTEGER NOT NULL, username TEXT NOT NULL, activated INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS deliveries (update_id INTEGER PRIMARY KEY, state TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_deliveries_ts ON deliveries(ts);
CREATE TABLE IF NOT EXISTS recent_events (kind TEXT NOT NULL, chat_id INTEGER NOT NULL, event_key TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(kind,chat_id,event_key));
CREATE INDEX IF NOT EXISTS idx_recent_events_ts ON recent_events(ts);
CREATE TABLE IF NOT EXISTS rate_events (chat_id INTEGER NOT NULL,user_id INTEGER NOT NULL,event_id INTEGER NOT NULL,ts INTEGER NOT NULL,PRIMARY KEY(chat_id,user_id,event_id));
CREATE INDEX IF NOT EXISTS idx_rate_events_ts ON rate_events(ts);

CREATE TABLE IF NOT EXISTS message_originals (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, original_json TEXT NOT NULL, platform TEXT, provider TEXT, ts INTEGER NOT NULL, PRIMARY KEY(chat_id,bot_msg_id));
CREATE INDEX IF NOT EXISTS idx_message_originals_ts ON message_originals(ts);
CREATE TABLE IF NOT EXISTS provider_health (platform TEXT NOT NULL, provider TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0, cooldown_until INTEGER NOT NULL DEFAULT 0, checked_at INTEGER NOT NULL, last_success_at INTEGER NOT NULL DEFAULT 0, last_status INTEGER, evidence TEXT NOT NULL, PRIMARY KEY(platform,provider));
CREATE TABLE IF NOT EXISTS provider_probe_cursor (id INTEGER PRIMARY KEY CHECK(id=1), cursor INTEGER NOT NULL, slot INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS post_controls (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, source_msg_id INTEGER NOT NULL, user_id INTEGER NOT NULL, state_json TEXT NOT NULL, ts INTEGER NOT NULL, lock_until INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(chat_id,bot_msg_id), UNIQUE(chat_id,source_msg_id));
CREATE INDEX IF NOT EXISTS idx_post_controls_ts ON post_controls(ts);

CREATE TABLE IF NOT EXISTS post_operations (operation_id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, desired_json TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_post_operations_message ON post_operations(chat_id,bot_msg_id,state);
CREATE INDEX IF NOT EXISTS idx_post_operations_ts ON post_operations(ts);
CREATE TABLE IF NOT EXISTS post_activity (chat_id INTEGER NOT NULL, bot_msg_id INTEGER NOT NULL, last_action_at INTEGER NOT NULL, PRIMARY KEY(chat_id,bot_msg_id));

CREATE TABLE IF NOT EXISTS free_daily_usage (day TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0, rows_read INTEGER NOT NULL DEFAULT 0, rows_written INTEGER NOT NULL DEFAULT 0, storage_bytes INTEGER NOT NULL DEFAULT 0);
