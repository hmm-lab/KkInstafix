"""Copy provider/tracking configuration and the SQLite schema without running bot.py."""
import ast
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
values={}
for filename in ['providers.py','bot.py']:
    for node in ast.parse((root/filename).read_text()).body:
        targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
        for target in targets:
            if isinstance(target,ast.Name):
                try: values[target.id]=ast.literal_eval(node.value)
                except (ValueError,TypeError): pass
keys=['PROVIDER_REVISION','PROVIDERS','PLATFORM_EMOJI','TRACKING','PLATFORM_TRACKING','INSTAGRAM_CONTENT_QUERY','INSTAGRAM_CONTENT_PATH','GENERIC_TRACKING','YOUTUBE_HOSTS','YOUTUBE_TRACKING','AMAZON_TLDS','AMAZON_TRACKING','EBAY_TLDS','EBAY_TRACKING','ALIEXPRESS_DOMAINS','ALIEXPRESS_TRACKING','LINKEDIN_TRACKING','PINTEREST_DOMAINS','PINTEREST_TRACKING','APPLE_MUSIC_TRACKING','VIMEO_TRACKING','SOUNDCLOUD_TRACKING','SHORT_LINK_DOMAINS']
(root/'cloudflare/src/config.js').write_text('// Generated from existing Python configuration; no provider changes.\n'+''.join('export const '+k+' = '+json.dumps(values[k],ensure_ascii=False,default=sorted)+';\n' for k in keys))
module=ast.parse((root/'database.py').read_text())
func=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='init_db')
call=next(n for n in ast.walk(func) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='executescript')
schema=ast.literal_eval(call.args[0])
(root/'cloudflare/schema.sql').write_text(schema+'''
CREATE TABLE IF NOT EXISTS runtime_config (id INTEGER PRIMARY KEY CHECK(id=1), token_cipher TEXT NOT NULL, bot_id INTEGER NOT NULL, username TEXT NOT NULL, activated INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS deliveries (update_id INTEGER PRIMARY KEY, state TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_deliveries_ts ON deliveries(ts);
CREATE TABLE IF NOT EXISTS recent_events (kind TEXT NOT NULL, chat_id INTEGER NOT NULL, event_key TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY(kind,chat_id,event_key));
CREATE INDEX IF NOT EXISTS idx_recent_events_ts ON recent_events(ts);
CREATE TABLE IF NOT EXISTS rate_events (chat_id INTEGER NOT NULL,user_id INTEGER NOT NULL,event_id INTEGER NOT NULL,ts INTEGER NOT NULL,PRIMARY KEY(chat_id,user_id,event_id));
CREATE INDEX IF NOT EXISTS idx_rate_events_ts ON rate_events(ts);
''')
