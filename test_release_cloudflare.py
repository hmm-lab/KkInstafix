"""Test the release protocol and migration contract with local fixtures."""
import json
import sqlite3
from pathlib import Path

import pytest

from tools import release_cloudflare as release
from tools.d1_release import LEDGER, SchemaError, migrate

CLOUDFLARE = Path(__file__).parent / 'cloudflare'
CONFIG = json.loads((CLOUDFLARE / 'deployment.json').read_text())
SCHEMA = (CLOUDFLARE / 'schema.sql').read_text()
MIGRATIONS = sorted((CLOUDFLARE / 'migrations').glob('*.sql'))
BUILD = 'a' * 40
OLD = {'id': 'old-deployment', 'versions': release.deployment_versions('old-version')}
NEW = {'id': 'new-deployment', 'versions': release.deployment_versions('new-version')}
COMPETING = {'id': 'competing-deployment', 'versions': release.deployment_versions('competing-version')}


class LocalD1:
    def __init__(self, sql):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(sql)
        self.calls = []

    def query(self, sql):
        self.calls.append(sql)
        with self.db:
            return [[dict(row) for row in self.db.execute(statement)] for statement in sql.split(';') if statement.strip()]


def before_migration(*paths):
    return SCHEMA[: -sum(len(path.read_text()) + 1 for path in paths)]


class FakeClient:
    config = CONFIG
    script = '/test-worker'

    def __init__(self):
        self.active = OLD
        self.db = LocalD1(before_migration(MIGRATIONS[-1]))
        self.query = self.db.query
        self.calls = []
        self.competing = False
        self.unknown = False
        self.receipt = {'confirmed': True, 'build': BUILD}
        self.build = BUILD

    def current(self):
        return self.active

    def check_settings(self):
        self.calls.append(('CHECK', 'settings', None))

    def request(self, method, path, body=None, content_type=None, public=False, legacy=False):
        self.calls.append((method, path, body))
        if path == '/health':
            return {'version': '2.4.1', **({'build': self.build} if self.active == NEW else {})}
        if path == '/admin/status':
            assert legacy == (self.active == OLD)
            return {'active': True, 'bindings_ready': True,
                    'build': self.build if self.active == NEW else None,
                    'webhook': {'url': CONFIG['url'] + '/webhook', 'pending_update_count': 0}}
        if path.startswith('/admin/status?release_check='):
            return self.receipt
        if method == 'POST' and path.endswith('/versions?bindings_inherit=strict'):
            return {'id': 'new-version'}
        if method == 'POST' and path.endswith('/deployments'):
            assert body['strategy'] == 'percentage'
            if body['versions'] == OLD['versions']:
                self.active = OLD
                return {'id': 'rollback'}
            assert body['versions'] == NEW['versions']
            self.active = COMPETING if self.competing else NEW
            if self.unknown:
                raise release.ReleaseError('response lost')
            return {'id': NEW['id']}
        raise AssertionError((method, path))


@pytest.fixture(autouse=True)
def no_real_waits(monkeypatch):
    monkeypatch.setattr(release.time, 'sleep', lambda _: None)


def deploy(client, tmp_path, *, timeout=5):
    return release.deploy(client, 'bundle', '2.4.1', BUILD, SCHEMA, MIGRATIONS,
                          tmp_path / 'rollback.json', timeout)


def test_release_records_the_returned_ids_and_requires_a_telegram_receipt(tmp_path):
    client = FakeClient()
    result = deploy(client, tmp_path)
    artifact = json.loads((tmp_path / 'rollback.json').read_text())
    assert result['build'] == BUILD
    assert artifact['previous'] == OLD
    assert artifact['candidate'] == NEW
    assert any(path.startswith('/admin/status?release_check=') for _, path, _ in client.calls)
    assert client.query(f'SELECT COUNT(*) AS n FROM {LEDGER}')[0][0]['n'] == len(MIGRATIONS)


def test_release_never_rolls_back_the_other_deployment_seen_after_activation(tmp_path):
    client = FakeClient()
    client.competing = True
    with pytest.raises(release.ReleaseError, match='active deployment or version changed'):
        deploy(client, tmp_path)
    assert client.active == COMPETING
    assert json.loads((tmp_path / 'rollback.json').read_text())['candidate'] == NEW
    assert sum(path.endswith('/deployments') for _, path, _ in client.calls) == 1


def test_manual_rollback_requires_the_owned_version_inside_the_deployment():
    client = FakeClient()
    client.active = {'id': NEW['id'], 'versions': COMPETING['versions']}
    with pytest.raises(release.ReleaseError, match='active deployment or version changed'):
        release.rollback(client, {'candidate': NEW, 'previous': OLD})
    assert not client.calls


def test_release_does_not_infer_ownership_after_an_ambiguous_activation(tmp_path):
    client = FakeClient()
    client.unknown = True
    with pytest.raises(release.ReleaseError, match='outcome uncertain'):
        deploy(client, tmp_path)
    assert 'candidate' not in json.loads((tmp_path / 'rollback.json').read_text())
    assert sum(path.endswith('/deployments') for _, path, _ in client.calls) == 1


def test_matching_semver_with_wrong_build_rolls_back_the_owned_candidate(tmp_path):
    client = FakeClient()
    client.build = 'b' * 40
    with pytest.raises(release.ReleaseError, match='build/bindings'):
        deploy(client, tmp_path)
    assert client.active == OLD


def test_missing_telegram_receipt_rolls_back_the_owned_candidate(tmp_path):
    client = FakeClient()
    client.receipt = {}
    with pytest.raises(release.ReleaseError, match='Telegram webhook update'):
        deploy(client, tmp_path, timeout=0)
    assert client.active == OLD


def test_release_rejects_a_split_traffic_baseline(tmp_path):
    client = FakeClient()
    client.active = {'id': 'split', 'versions': [{'version_id': 'one', 'percentage': 50},
                                                 {'version_id': 'two', 'percentage': 50}]}
    with pytest.raises(release.ReleaseError, match='100%'):
        deploy(client, tmp_path)
    assert not client.calls


@pytest.mark.parametrize('initial_schema', [SCHEMA, before_migration(MIGRATIONS[-1])])
def test_schema_migration_preserves_data_and_runs_once(initial_schema):
    fixture = LocalD1(initial_schema)
    fixture.query("INSERT INTO chat_settings(chat_id, rate_limit) VALUES (71, 11)")
    migrate(fixture.query, SCHEMA, MIGRATIONS)
    assert fixture.query("SELECT rate_limit FROM chat_settings WHERE chat_id=71") == [[{'rate_limit': 11}]]
    assert fixture.query(f"SELECT COUNT(*) AS n FROM {LEDGER}") == [[{'n': len(MIGRATIONS)}]]
    fixture.calls.clear()
    migrate(fixture.query, SCHEMA, MIGRATIONS)
    assert not any('CREATE ' in sql or 'INSERT ' in sql for sql in fixture.calls)


def test_release_stops_on_incompatible_existing_schema_before_upload(tmp_path):
    client = FakeClient()
    client.query('DROP TABLE free_daily_usage; CREATE TABLE free_daily_usage (invalid TEXT)')
    with pytest.raises(SchemaError, match='Incompatible D1 schema: free_daily_usage'):
        deploy(client, tmp_path)
    assert not any(path.endswith('/versions?bindings_inherit=strict') for _, path, _ in client.calls)


def test_migration_rejects_an_altered_ledgered_file():
    fixture = LocalD1(SCHEMA)
    migrate(fixture.query, SCHEMA, MIGRATIONS)
    fixture.query(f"UPDATE {LEDGER} SET sha256='incorrect' WHERE name='{MIGRATIONS[-1].name}'")
    with pytest.raises(SchemaError, match='Previously applied migration changed'):
        migrate(fixture.query, SCHEMA, MIGRATIONS)


def test_release_multipart_preserves_required_bindings_and_attests_to_build():
    meta = release.metadata(CONFIG, BUILD)
    assert {b['name'] for b in meta['bindings'] if b['type'] == 'inherit'} == {
        'ADMIN_HASH', 'CONFIG_KEY', 'RELEASE_CHAT_ID', 'WEBHOOK_SECRET'}
    assert {b['type'] for b in meta['bindings']} == {'d1', 'inherit', 'plain_text'}
    assert 'limits' not in meta
    assert meta['usage_model'] == 'standard'
    body, kind = release.upload_body(CONFIG, 'export default {};', BUILD)
    assert kind.startswith('multipart/form-data; boundary=')
    for value in ['name="metadata"', 'filename="worker.js"', 'export default {};', BUILD]:
        assert value.encode() in body


def test_release_settings_rejects_cron_drift_and_sampled_traces(monkeypatch):
    client = release.Client('api-key', 'admin-key', CONFIG)
    responses = {'schedules': {'schedules': [{'cron': CONFIG['cron']}]},
                 'script-settings': {'observability': {'enabled': True, 'traces': {'enabled': True, 'head_sampling_rate': 0}}}}
    monkeypatch.setattr(client, 'request', lambda method, path: responses[path.rsplit('/', 1)[-1]])
    client.check_settings()
    responses['script-settings']['observability']['traces']['head_sampling_rate'] = 0.1
    with pytest.raises(release.ReleaseError, match='sampled Worker traces'):
        client.check_settings()
    responses['schedules']['schedules'] = []
    with pytest.raises(release.ReleaseError, match='cron'):
        client.check_settings()


def test_release_version_guard_catches_missing_documentation(tmp_path, monkeypatch):
    from tools import check_release
    (tmp_path / 'cloudflare/src').mkdir(parents=True)
    (tmp_path / 'cloudflare/src/version.js').write_text("export const VERSION='2.2.0';")
    (tmp_path / 'README.md').write_text('version 2.1.0')
    monkeypatch.setattr(check_release, 'ROOT', tmp_path)
    with pytest.raises(SystemExit, match='must document Worker 2.2.0'):
        check_release.check()


def test_release_rejects_an_accidental_paid_size_cpu_allowance():
    with pytest.raises(release.ReleaseError, match='Free-tier policy'):
        release.metadata({**CONFIG, 'limits': {'cpu_ms': 30000}}, BUILD)
