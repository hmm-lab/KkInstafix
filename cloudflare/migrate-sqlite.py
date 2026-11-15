"""Export an existing Railway SQLite DB for D1, excluding credentials/test data.
Usage: python migrate-sqlite.py /path/to/real/bot_data.sqlite3 output.sql
Review and apply output.sql to the D1 database before activation.
"""
import sqlite3
import sys
from pathlib import Path
TABLES={'chat_settings','provider_settings','blocked_users','disabled_platforms',
        'platform_overrides','optout_users','chat_stats','rewritten_messages','user_settings'}
def export(source,target):
    conn=sqlite3.connect('file:'+str(Path(source).resolve())+'?mode=ro',uri=True)
    statements=[]
    for table in sorted(TABLES):
        if not conn.execute('SELECT 1 FROM sqlite_master WHERE name=? AND type=\'table\'',(table,)).fetchone():
            continue
        columns=[r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
        for row in conn.execute(f'SELECT * FROM {table}'):
            literals=[conn.execute('SELECT quote(?)',(value,)).fetchone()[0] for value in row]
            statements.append(f'INSERT OR REPLACE INTO {table} ({",".join(columns)}) VALUES ({",".join(literals)});')
    statements.append('INSERT OR IGNORE INTO platform_overrides SELECT chat_id,platform,0 FROM disabled_platforms;')
    Path(target).write_text('\n'.join(statements)+'\n')
    conn.close()
if __name__=='__main__':
    export(sys.argv[1],sys.argv[2])
