"""The Cloudflare exporter preserves old settings without copying credentials."""
import runpy
import sqlite3
from pathlib import Path

def test_cloudflare_export_keeps_optouts_and_quotes_values(tmp_path):
    source=tmp_path/'old.sqlite3'
    conn=sqlite3.connect(source)
    conn.executescript("CREATE TABLE optout_users(chat_id INTEGER,user_id INTEGER); CREATE TABLE user_settings(user_id INTEGER,chat_id INTEGER,key TEXT,value TEXT); CREATE TABLE runtime_config(token TEXT);")
    conn.execute('INSERT INTO optout_users VALUES(?,?)',(-1001,5))
    conn.execute('INSERT INTO user_settings VALUES(?,?,?,?)',(5,-1001,'sender_mode',"O'Brien"))
    conn.execute('INSERT INTO runtime_config VALUES(?)',('secret-not-for-export',))
    conn.commit();conn.close()
    dest=tmp_path/'migration.sql'
    module=runpy.run_path(str(Path(__file__).parent/'cloudflare/migrate-sqlite.py'))
    module['export'](source,dest)
    sql=dest.read_text()
    assert 'secret-not-for-export' not in sql
    restored=sqlite3.connect(':memory:')
    restored.executescript('CREATE TABLE optout_users(chat_id INTEGER,user_id INTEGER); CREATE TABLE user_settings(user_id INTEGER,chat_id INTEGER,key TEXT,value TEXT); CREATE TABLE platform_overrides(chat_id INTEGER,platform TEXT,enabled INTEGER); CREATE TABLE disabled_platforms(chat_id INTEGER,platform TEXT);')
    restored.executescript(sql)
    assert restored.execute('SELECT * FROM optout_users').fetchone()==(-1001,5)
    assert restored.execute('SELECT value FROM user_settings').fetchone()[0]=="O'Brien"
    restored.close()
