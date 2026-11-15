"""Deploy the tested Worker; verify readiness/webhook and roll back code on failure.

Uses CLOUDFLARE_API_TOKEN and KKINSTAFIX_ADMIN_KEY from the environment.
Secrets are inherited by the Worker and are never printed or saved in artifacts.
Additive database migrations are intentionally retained during code rollback.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


class ReleaseError(Exception):
    pass


class Client:
    def __init__(self, token, admin, config):
        self.token, self.admin, self.config = token, admin, config

    def request(self, method, path, body=None, content_type='application/json', public=False):
        endpoint = self.config['url'] + path if public else 'https://api.cloudflare.com/client/v4' + path
        credential = self.admin if public else self.token
        headers = {'Authorization': 'Bearer ' + credential, 'Content-Type': content_type, 'User-Agent': 'KkInstafix-release'}
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
        try:
            with urlopen(Request(endpoint, data=body, headers=headers, method=method), timeout=45) as response:
                data = json.loads(response.read(1024 * 1024))
        except (HTTPError, URLError, TimeoutError, ValueError):
            # HTTP bodies can contain credentials or private request data.
            raise ReleaseError(f'{method} {path}: request failed') from None
        if not public:
            if not data.get('success'):
                raise ReleaseError(f'{method} {path}: API rejected request')
            return data['result']
        return data

    @property
    def script(self):
        return f"/accounts/{self.config['account_id']}/workers/scripts/{self.config['worker']}"

    def deployments(self):
        return self.request('GET', self.script + '/deployments')['deployments']


def metadata(config):
    return {'main_module': 'worker.js', 'compatibility_date': config['compatibility_date'],
            'usage_model': config['usage_model'],
            'observability': {'enabled': True, 'logs': {'enabled': True, 'invocation_logs': True, 'head_sampling_rate': 1},
                              'traces': {'enabled': True, 'head_sampling_rate': 0}},
            'bindings': [{'type': 'd1', 'name': 'DB', 'database_id': config['database_id']},
                         *[{'type': 'inherit', 'name': name} for name in ['CONFIG_KEY', 'SETUP_HASH', 'WEBHOOK_SECRET']],
                         {'type': 'plain_text', 'name': 'WEBHOOK_URL', 'text': config['url'] + '/webhook'}]}


def upload_body(config, bundle):
    boundary = 'kkinstafix-release-' + os.urandom(16).hex()
    parts = []
    for name, content, kind, filename in [('metadata', json.dumps(metadata(config)), 'application/json', ''),
                                           ('worker.js', bundle, 'application/javascript+module', '; filename="worker.js"')]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"{filename}\r\nContent-Type: {kind}\r\n\r\n{content}\r\n')
    return (''.join(parts) + f'--{boundary}--\r\n').encode(), 'multipart/form-data; boundary=' + boundary


def verify(client, version):
    health = client.request('GET', '/health', public=True)
    status = client.request('POST', '/admin/status', {}, public=True)
    if health.get('version') != version or not health.get('active') or not status.get('active'):
        raise ReleaseError('Deployment readiness/version verification failed')
    webhook = status.get('webhook', {})
    if webhook.get('url') != client.config['url'] + '/webhook':
        raise ReleaseError('Webhook target verification failed')
    # Historical webhook errors are not evidence that the new code failed.
    return {'version': version, 'active': True, 'pending_updates': webhook.get('pending_update_count')}


def rollback(client, previous, expected_deployment):
    current = client.deployments()[0]
    if current['id'] != expected_deployment:
        raise ReleaseError('Another deployment occurred; automatic rollback refused to overwrite it')
    return client.request('POST', client.script + '/deployments',
                          {'strategy': 'percentage', 'versions': previous['versions']})


def deploy(client, bundle, version, migrations, artifact):
    current = client.deployments()[0]
    before = {'id': current['id'], 'versions': current['versions']}
    old_health = client.request('GET', '/health', public=True)
    if len(before.get('versions', [])) != 1 or before['versions'][0].get('percentage') != 100:
        raise ReleaseError('A single 100% current deployment is required for safe rollback')
    # Confirm credentials/readiness before changing the database or code.
    verify(client, old_health['version'])
    artifact.write_text(json.dumps({'previous_deployment': before, 'previous_version': old_health['version']}, indent=2))
    db_path = f"/accounts/{client.config['account_id']}/d1/database/{client.config['database_id']}/query"
    for migration in migrations:
        results = client.request('POST', db_path, {'sql': migration.read_text()})
        if any(row.get('success') is False for row in results):
            raise ReleaseError('Database migration rejected; upload cancelled')
    # Check that production did not change during migration.
    if client.deployments()[0]['id'] != before['id']:
        raise ReleaseError('Production changed during preparation; upload cancelled')
    body, content_type = upload_body(client.config, bundle)
    # A transport timeout has an ambiguous result. Do not blindly upload again.
    try:
        client.request('PUT', client.script, body, content_type)
    except ReleaseError:
        after = client.deployments()[0]
        if after['id'] != before['id']:
            raise ReleaseError('Upload outcome uncertain; inspect production before retrying') from None
        raise
    after = client.deployments()[0]
    if after['id'] == before['id']:
        raise ReleaseError('Upload did not create a new deployment')
    state = json.loads(artifact.read_text())
    state['new_deployment_id'] = after['id']
    artifact.write_text(json.dumps(state, indent=2))
    for attempt in range(3):
        try:
            result = verify(client, version)
            print(json.dumps({'deployment': after['id'], **result}))
            return result
        except ReleaseError:
            if attempt < 2:
                time.sleep(2)
    rollback(client, before, after['id'])
    verify(client, old_health['version'])
    raise ReleaseError('New deployment failed verification; previous Worker restored. Additive migrations retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--rollback', type=Path, help='Restore version from a previous rollback artifact, with deployment lease')
    parser.add_argument('--artifact', type=Path, default=Path('release-rollback.json'))
    args = parser.parse_args()
    config = json.loads((ROOT / 'cloudflare/deployment.json').read_text())
    version = re.search(r"VERSION='([^']+)'", (ROOT / 'cloudflare/src/version.js').read_text())[1]
    bundle = '' if args.rollback else (ROOT / 'cloudflare/dist/worker.js').read_text()
    if not args.rollback and version not in bundle:
        raise ReleaseError('Build the current Worker before releasing')
    if args.dry_run:
        print(json.dumps({'version': version, 'worker': config['worker'], 'migrations': len(list((ROOT / 'cloudflare/migrations').glob('*.sql'))), 'network_requests': 0}))
        return
    token, admin = os.environ.get('CLOUDFLARE_API_TOKEN'), os.environ.get('KKINSTAFIX_ADMIN_KEY')
    if not token or not admin:
        raise ReleaseError('Set CLOUDFLARE_API_TOKEN and KKINSTAFIX_ADMIN_KEY in release secrets')
    client = Client(token, admin, config)
    if args.rollback:
        state = json.loads(args.rollback.read_text())
        rollback(client, state['previous_deployment'], state['new_deployment_id'])
        print(json.dumps(verify(client, state['previous_version'])))
    else:
        deploy(client, bundle, version, sorted((ROOT / 'cloudflare/migrations').glob('*.sql')), args.artifact)


if __name__ == '__main__':
    try:
        main()
    except ReleaseError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
