"""Release safety checks without Cloudflare credentials or outbound requests."""
import json
from pathlib import Path

import pytest

from tools import release_cloudflare as release

CONFIG = json.loads((Path(__file__).parent / 'cloudflare/deployment.json').read_text())
OLD = {'id': 'old-deployment', 'versions': [{'version_id': 'old-version', 'percentage': 100}]}
NEW = {'id': 'new-deployment', 'versions': [{'version_id': 'new-version', 'percentage': 100}]}


class FakeClient:
    config = CONFIG
    script = '/test-worker'

    def __init__(self, wrong_version=False, concurrent=False, failed_migration=False, upload_timeout=False):
        self.current, self.version = OLD, '2.1.0'
        self.wrong_version, self.concurrent = wrong_version, concurrent
        self.failed_migration, self.upload_timeout = failed_migration, upload_timeout
        self.calls, self.post_upload_checks = [], 0

    def deployments(self):
        if self.current == NEW and self.concurrent:
            self.post_upload_checks += 1
            if self.post_upload_checks > 1:
                return [{'id': 'someone-else', 'versions': []}]
        return [self.current]

    def request(self, method, path, body=None, content_type=None, public=False):
        self.calls.append((method, path, body))
        if path == '/health':
            return {'version': self.version, 'active': True}
        if path == '/admin/status':
            return {'active': True, 'webhook': {'url': CONFIG['url'] + '/webhook', 'pending_update_count': 0}}
        if path.endswith('/query'):
            if self.failed_migration:
                raise release.ReleaseError('migration failed')
            return []
        if method == 'PUT':
            self.current, self.version = NEW, 'wrong' if self.wrong_version else '2.2.0'
            if self.upload_timeout:
                raise release.ReleaseError('upload timed out')
            return {}
        if path.endswith('/deployments') and method == 'POST':
            self.current, self.version = OLD, '2.1.0'
            assert body == {'strategy': 'percentage', 'versions': OLD['versions']}
            return {'id': 'rollback'}
        raise AssertionError((method, path))


def migration(tmp_path):
    sql = tmp_path / 'migration.sql'
    sql.write_text('CREATE TABLE IF NOT EXISTS sample(id INTEGER);')
    return [sql]


def test_release_deploys_migrations_before_upload_and_saves_secret_free_rollback(tmp_path):
    client = FakeClient()
    artifact = tmp_path / 'rollback.json'
    result = release.deploy(client, 'bundle', '2.2.0', migration(tmp_path), artifact)
    assert result['active']
    methods = [method for method, _, _ in client.calls]
    assert methods.index('PUT') > next(i for i, (_, p, _) in enumerate(client.calls) if p.endswith('/query'))
    state = json.loads(artifact.read_text())
    assert state['previous_deployment'] == OLD
    assert state['new_deployment_id'] == NEW['id']
    assert 'secret' not in artifact.read_text().lower()


def test_release_verification_failure_restores_previous_code(tmp_path, monkeypatch):
    monkeypatch.setattr(release.time, 'sleep', lambda _: None)
    client = FakeClient(wrong_version=True)
    with pytest.raises(release.ReleaseError, match='previous Worker restored'):
        release.deploy(client, 'bundle', '2.2.0', migration(tmp_path), tmp_path / 'rollback.json')
    assert client.current == OLD
    assert any(m == 'POST' and p.endswith('/deployments') for m, p, _ in client.calls)


def test_release_rollback_never_overwrites_a_concurrent_deployment(tmp_path, monkeypatch):
    monkeypatch.setattr(release.time, 'sleep', lambda _: None)
    client = FakeClient(wrong_version=True, concurrent=True)
    with pytest.raises(release.ReleaseError, match='Another deployment'):
        release.deploy(client, 'bundle', '2.2.0', migration(tmp_path), tmp_path / 'rollback.json')
    assert not any(m == 'POST' and p.endswith('/deployments') for m, p, _ in client.calls)


def test_release_stops_before_upload_if_migration_fails(tmp_path):
    client = FakeClient(failed_migration=True)
    with pytest.raises(release.ReleaseError, match='migration failed'):
        release.deploy(client, 'bundle', '2.2.0', migration(tmp_path), tmp_path / 'rollback.json')
    assert not any(m == 'PUT' for m, _, _ in client.calls)


def test_release_does_not_repeat_an_ambiguous_upload(tmp_path):
    client = FakeClient(upload_timeout=True)
    with pytest.raises(release.ReleaseError, match='outcome uncertain'):
        release.deploy(client, 'bundle', '2.2.0', migration(tmp_path), tmp_path / 'rollback.json')
    assert sum(m == 'PUT' for m, _, _ in client.calls) == 1


def test_release_rejects_a_split_traffic_baseline(tmp_path):
    client = FakeClient()
    client.current = {'id': 'split', 'versions': [{'version_id': 'one', 'percentage': 50}, {'version_id': 'two', 'percentage': 50}]}
    with pytest.raises(release.ReleaseError, match='100%'):
        release.deploy(client, 'bundle', '2.2.0', [], tmp_path / 'rollback.json')
    assert not any(m == 'PUT' for m, _, _ in client.calls)


def test_release_metadata_preserves_secrets_and_disables_token_url_tracing():
    meta = release.metadata(CONFIG)
    assert {b['name'] for b in meta['bindings'] if b['type'] == 'inherit'} == {'CONFIG_KEY', 'SETUP_HASH', 'WEBHOOK_SECRET'}
    assert meta['observability']['traces'] == {'enabled': True, 'head_sampling_rate': 0}
    assert meta['usage_model'] == 'standard'
    assert all('secret_text' != b['type'] for b in meta['bindings'])


def test_release_multipart_upload_contains_bundle_and_metadata():
    body, kind = release.upload_body(CONFIG, 'export default {};')
    assert kind.startswith('multipart/form-data; boundary=')
    assert b'name="metadata"' in body
    assert b'filename="worker.js"' in body
    assert b'export default {};' in body
    assert b'CONFIG_KEY' in body and b'"type": "inherit"' in body


def test_release_version_guard_catches_missing_documentation(tmp_path, monkeypatch):
    from tools import check_release
    (tmp_path / 'cloudflare/src').mkdir(parents=True)
    (tmp_path / 'cloudflare/src/version.js').write_text("export const VERSION='2.2.0';")
    (tmp_path / 'README.md').write_text('version 2.1.0')
    monkeypatch.setattr(check_release, 'ROOT', tmp_path)
    with pytest.raises(SystemExit, match='must document Worker 2.2.0'):
        check_release.check()


def test_free_tier_release_metadata_enforces_cpu_and_samples_logs():
    meta = release.metadata(CONFIG)
    assert 'limits' not in meta
    assert CONFIG['free_tier_policy']['cpu_ms'] == 10
    assert meta['observability']['logs']['head_sampling_rate'] == 0.1
    assert {b['type'] for b in meta['bindings']} == {'d1', 'inherit', 'plain_text'}


def test_release_rejects_an_accidental_paid_size_cpu_allowance():
    with pytest.raises(release.ReleaseError, match='Free-tier policy'):
        release.metadata({**CONFIG, 'limits': {'cpu_ms': 30000}})
