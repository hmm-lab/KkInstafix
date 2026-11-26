"""Check the target D1 schema and apply versioned migrations once."""
from contextlib import closing
from hashlib import sha256
import re
import sqlite3

LEDGER = 'kkinstafix_schema_migrations'
LEDGER_SQL = f'CREATE TABLE IF NOT EXISTS {LEDGER} (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)'
NAME = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*\Z')
LEGACY_MIGRATIONS = frozenset({
    '0002-improvements.sql', '0003-post-controls.sql',
    '0004-edit-recovery.sql', '0005-free-budget.sql',
})


class SchemaError(Exception):
    pass


def statements(objects):
    for kind, name in objects:
        if not NAME.fullmatch(name):
            raise SchemaError('Unexpected D1 schema identifier')
        pragma = 'table_info' if kind == 'table' else 'index_info'
        yield f'PRAGMA {pragma}("{name}")'


def shape(kind, rows):
    if kind == 'table':
        # Older deployments may retain a previous default for text_spam.
        return tuple((r['name'], r['type'].upper(), r['notnull'], r['pk'],
                      None if r['name'] == 'text_spam' else r['dflt_value']) for r in rows)
    return tuple(r['name'] for r in rows)


def local_contract(db):
    objects = [tuple(row) for row in db.execute(
        "SELECT type,name FROM sqlite_schema WHERE type IN ('table','index') ORDER BY type,name")]
    return {obj: shape(obj[0], db.execute(sql)) for obj, sql in zip(objects, statements(objects))}


def contracts(schema, migrations):
    texts = [(path.name, path.read_text()) for path in migrations]
    base = schema
    for name, sql in reversed(texts):
        suffix = '\n' + sql
        if not base.endswith(suffix):
            raise SchemaError(f'Generated D1 schema is missing {name}')
        base = base[:-len(suffix)]
    with closing(sqlite3.connect(':memory:')) as db:
        db.row_factory = sqlite3.Row
        db.executescript(base)
        before = previous = local_contract(db)
        changes = {}
        for name, sql in texts:
            db.executescript(sql)
            current = local_contract(db)
            changes[name] = {obj: value for obj, value in current.items() if previous.get(obj) != value}
            previous = current
        db.execute(LEDGER_SQL)
        expected = local_contract(db)
    return before, expected, changes, texts


def migrate(query, schema, migrations, *, apply=True):
    baseline, expected, changes, texts = contracts(schema, migrations)
    db_objects = {(row['type'], row['name']) for row in query(
        "SELECT type,name FROM sqlite_schema WHERE type IN ('table','index') ORDER BY type,name")[0]}
    existing = sorted(db_objects & expected.keys())
    rows = query(';\n'.join(statements(existing))) if existing else []
    remote = {obj: shape(obj[0], result) for obj, result in zip(existing, rows, strict=True)}
    ledger_object = ('table', LEDGER)

    accepted = {obj: {signature} for obj, signature in expected.items()}
    for contract in [baseline, *changes.values()]:
        for obj, signature in contract.items():
            accepted[obj].add(signature)
    incompatible = [name for (kind, name), signature in remote.items() if signature not in accepted[(kind, name)]]
    missing_base = [name for kind, name in baseline if (kind, name) not in remote]
    if incompatible or missing_base:
        raise SchemaError('Incompatible D1 schema: ' + ', '.join(sorted(set(incompatible + missing_base))))

    recorded = {}
    if ledger_object in remote:
        recorded = {r['name']: r['sha256'] for r in query(f'SELECT name,sha256 FROM {LEDGER}')[0]}
    for name, sql in texts:
        if name in recorded and recorded[name] != sha256(sql.encode()).hexdigest():
            raise SchemaError(f'Previously applied migration changed: {name}')
        if name in recorded and any(obj not in remote for obj in changes[name]):
            raise SchemaError(f'Previously applied migration is missing schema objects: {name}')

    # Upgrades from the prerelease process may have these create-only migrations
    # already applied. Record them only after their full schema validates.
    missing = []
    for name, sql in texts:
        if name in recorded:
            continue
        present = changes[name] and all(remote.get(obj) == value for obj, value in changes[name].items())
        missing.append((name, sql, name in LEGACY_MIGRATIONS and present))
    if not apply:
        if any(not adopted for _, _, adopted in missing):
            raise SchemaError('Required D1 migrations are missing')
        if any(remote.get(obj) != value for obj, value in expected.items() if obj[1] != LEDGER and obj[1] != f'sqlite_autoindex_{LEDGER}_1'):
            raise SchemaError('Target D1 schema differs from the release')
        return

    if ledger_object not in remote:
        query(LEDGER_SQL)
    for name, sql, adopted in missing:
        checksum = sha256(sql.encode()).hexdigest()
        if not re.fullmatch(r'[0-9]+-[a-z0-9-]+\.sql', name):
            raise SchemaError('Invalid migration filename')
        receipt = f"INSERT INTO {LEDGER} VALUES ('{name}', '{checksum}');"
        query(receipt if adopted else sql.rstrip() + '\n' + receipt)
    migrate(query, schema, migrations, apply=False)
