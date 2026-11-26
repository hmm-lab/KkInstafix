"""Deploy a tested Worker version, verify Telegram delivery and guard code rollback."""
import argparse
from hashlib import sha256
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from .d1_release import SchemaError, contracts, migrate
else:
    from d1_release import SchemaError, contracts, migrate

ROOT = Path(__file__).resolve().parent.parent
CLOUDFLARE = ROOT / 'cloudflare'


class ReleaseError(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token, admin, config, legacy_admin=None):
        self.token, self.admin, self.config = token, admin, config
        self.legacy_admin = legacy_admin or admin
        self.opener = build_opener(NoRedirects())

    def request(self, method, path, body=None, content_type='application/json', public=False, legacy=False):
        endpoint = self.config['url'] + path if public else 'https://api.cloudflare.com/client/v4' + path
        credential = (self.legacy_admin if legacy else self.admin) if public else self.token
        headers = {'Content-Type': content_type, 'User-Agent': 'KkInstafix-release'}
        if not public or method != 'GET':
            headers['Authorization'] = 'Bearer ' + credential
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
        try:
            with self.opener.open(Request(endpoint, data=body, headers=headers, method=method), timeout=30) as response:
                data = json.loads(response.read(1024 * 1024))
        except (HTTPError, URLError, TimeoutError, ValueError):
            raise ReleaseError(f'{method} {path.split("?")[0]}: request failed') from None
        if public:
            return data
        if not data.get('success'):
            raise ReleaseError(f'{method} {path}: API rejected request')
        return data['result']

    @property
    def script(self):
        return f"/accounts/{self.config['account_id']}/workers/scripts/{self.config['worker']}"

    def current(self):
        deployments = self.request('GET', self.script + '/deployments')['deployments']
        if not deployments:
            raise ReleaseError('An existing Worker deployment is required')
        return deployments[0]

    def query(self, sql):
        path = f"/accounts/{self.config['account_id']}/d1/database/{self.config['database_id']}/query"
        results = self.request('POST', path, {'sql': sql})
        if not results or any(result.get('success') is not True for result in results):
            raise ReleaseError('D1 did not confirm all statements')
        return [result.get('results', []) for result in results]

    def check_settings(self):
        items = self.request('GET', self.script + '/schedules')['schedules']
        if {item['cron'] for item in items} != {self.config['cron']}:
            raise ReleaseError('The target Worker cron differs from deployment configuration')
        settings = self.request('GET', self.script + '/script-settings')
        observability = settings.get('observability') or {}
        traces = observability.get('traces') or {}
        if observability.get('enabled') and traces.get('enabled') and traces.get('head_sampling_rate', 1) != 0:
            raise ReleaseError('Disable sampled Worker traces before releasing to protect Telegram token URLs')


def validate_config(config):
    url = urlsplit(config['url'])
    if (url.scheme != 'https' or not url.hostname or url.port or url.username or url.password or
            url.path or url.query or url.fragment):
        raise ReleaseError('Deployment URL must be an HTTPS origin')
    if config.get('usage_model') != 'standard' or config.get('limits'):
        raise ReleaseError('Free-tier policy forbids custom CPU limits or legacy usage models')
    if not re.fullmatch(r'[0-9a-f]{32}', config['account_id']) or not re.fullmatch(r'[a-z0-9-]+', config['worker']):
        raise ReleaseError('Invalid Cloudflare account or Worker name')
    if not re.fullmatch(r'[0-9a-f-]{36}', config['database_id']) or len(config['cron'].split()) != 5:
        raise ReleaseError('Invalid D1 database ID or cron schedule')


def metadata(config, build):
    validate_config(config)
    return {'main_module': 'worker.js', 'compatibility_date': config['compatibility_date'],
            'usage_model': config['usage_model'],
            'bindings': [{'type': 'd1', 'name': 'DB', 'database_id': config['database_id']},
                         *[{'type': 'inherit', 'name': name} for name in
                           ['ADMIN_HASH', 'CONFIG_KEY', 'RELEASE_CHAT_ID', 'WEBHOOK_SECRET']],
                         {'type': 'plain_text', 'name': 'WEBHOOK_URL', 'text': config['url'] + '/webhook'},
                         {'type': 'plain_text', 'name': 'RELEASE_BUILD', 'text': build}]}


def upload_body(config, bundle, build):
    boundary = 'kkinstafix-release-' + secrets.token_hex(16)
    parts = []
    for name, content, kind, filename in [('metadata', json.dumps(metadata(config, build)), 'application/json', ''),
                                           ('worker.js', bundle, 'application/javascript+module', '; filename="worker.js"')]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"{filename}\r\nContent-Type: {kind}\r\n\r\n{content}\r\n')
    return (''.join(parts) + f'--{boundary}--\r\n').encode(), 'multipart/form-data; boundary=' + boundary


def verify(client, version, build=None):
    health = client.request('GET', '/health', public=True)
    status = client.request('POST', '/admin/status', {}, public=True, legacy=build is None)
    if health.get('version') != version or not status.get('active'):
        raise ReleaseError('Deployment readiness/version verification failed')
    if build is not None and (health.get('build') != build or status.get('build') != build or not status.get('bindings_ready')):
        raise ReleaseError('Deployment build/bindings verification failed')
    webhook = status.get('webhook', {})
    if webhook.get('url') != client.config['url'] + '/webhook':
        raise ReleaseError('Webhook target verification failed')
    return {'version': version, 'build': build, 'active': True, 'pending_updates': webhook.get('pending_update_count')}


def deployment_versions(version_id):
    return [{'version_id': version_id, 'percentage': 100}]


def check_ownership(client, expected):
    current = client.current()
    if current.get('id') != expected['id'] or current.get('versions') != expected['versions']:
        raise ReleaseError('The active deployment or version changed')


def rollback(client, state):
    check_ownership(client, state['candidate'])
    client.request('POST', client.script + '/deployments',
                   {'strategy': 'percentage', 'versions': state['previous']['versions']})
    verify(client, state['previous_version'], state.get('previous_build'))


def telegram_check(client, candidate, build, timeout):
    nonce = secrets.token_hex(16)
    print(f'Send /releasecheck {nonce} from the configured Telegram release chat.', flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_ownership(client, candidate)
        try:
            receipt = client.request('POST', '/admin/status?release_check=' + nonce, {}, public=True)
        except ReleaseError:
            receipt = {}
        if receipt.get('confirmed') and receipt.get('build') == build:
            return
        time.sleep(5)
    raise ReleaseError('The expected build did not confirm a Telegram webhook update')


def deploy(client, bundle, version, build, schema, migrations, artifact, canary_timeout):
    before = client.current()
    if len(before.get('versions', [])) != 1 or before['versions'][0].get('percentage') != 100:
        raise ReleaseError('A single 100% current deployment is required for safe rollback')
    old_health = client.request('GET', '/health', public=True)
    verify(client, old_health['version'], old_health.get('build'))
    client.check_settings()
    state = {'previous': before, 'previous_version': old_health['version'], 'previous_build': old_health.get('build')}
    artifact.write_text(json.dumps(state, indent=2))
    migrate(client.query, schema, migrations)
    check_ownership(client, before)
    body, content_type = upload_body(client.config, bundle, build)
    version_id = client.request('POST', client.script + '/versions?bindings_inherit=strict', body, content_type)['id']
    check_ownership(client, before)
    versions = deployment_versions(version_id)
    try:
        deployment = client.request('POST', client.script + '/deployments', {'strategy': 'percentage', 'versions': versions})
    except ReleaseError:
        # A lost response cannot establish deployment ownership.
        raise ReleaseError('Activation outcome uncertain; inspect Cloudflare deployment history before retrying') from None
    candidate = {'id': deployment['id'], 'versions': versions}
    state['candidate'] = candidate
    artifact.write_text(json.dumps(state, indent=2))
    check_ownership(client, candidate)
    try:
        for attempt in range(3):
            try:
                result = verify(client, version, build)
                break
            except ReleaseError:
                if attempt == 2:
                    raise
                time.sleep(2)
        client.check_settings()
        telegram_check(client, candidate, build, canary_timeout)
        check_ownership(client, candidate)
    except ReleaseError:
        rollback(client, state)
        raise
    print(json.dumps({'deployment': candidate['id'], **result}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--rollback', type=Path, help='Restore the previous version from a rollback artifact')
    parser.add_argument('--artifact', type=Path, default=Path('release-rollback.json'))
    parser.add_argument('--target', choices=('production', 'staging'), default='production')
    parser.add_argument('--build', default=os.environ.get('GITHUB_SHA'))
    parser.add_argument('--canary-timeout', type=int, default=360)
    args = parser.parse_args()
    production = json.loads((CLOUDFLARE / 'deployment.json').read_text())
    config = production
    if args.target == 'staging':
        config = json.loads(os.environ.get('KKINSTAFIX_STAGING_CONFIG') or '{}')
        required = {'account_id', 'worker', 'url', 'database_id', 'compatibility_date', 'usage_model', 'cron'}
        if required - config.keys():
            raise ReleaseError('Set KKINSTAFIX_STAGING_CONFIG for the staging environment')
        if (config['account_id'], config['worker']) == (production['account_id'], production['worker']) or any(
                config[key] == production[key] for key in ['url', 'database_id']):
            raise ReleaseError('Staging must use its own Worker, URL and D1 database')
        if config['compatibility_date'] != production['compatibility_date']:
            raise ReleaseError('Staging must use the production compatibility date')
    validate_config(config)
    version = re.search(r"VERSION='([^']+)'", (CLOUDFLARE / 'src/version.js').read_text())[1]
    migrations = sorted((CLOUDFLARE / 'migrations').glob('*.sql'))
    schema = (CLOUDFLARE / 'schema.sql').read_text()
    bundle = '' if args.rollback else (CLOUDFLARE / 'dist/worker.js').read_text()
    if not args.rollback and version not in bundle:
        raise ReleaseError('Build the current Worker before releasing')
    build = args.build or sha256(bundle.encode()).hexdigest()
    if not re.fullmatch(r'[a-f0-9]{40,64}', build):
        raise ReleaseError('Invalid build identity')
    if args.dry_run:
        contracts(schema, migrations)
        upload_body(config, bundle, build)
        print(json.dumps({'version': version, 'build': build, 'worker': config['worker'],
                          'migrations': len(migrations), 'network_requests': 0}))
        return
    token, admin = os.environ.get('CLOUDFLARE_API_TOKEN'), os.environ.get('KKINSTAFIX_ADMIN_KEY')
    if not token or not admin:
        raise ReleaseError('Set CLOUDFLARE_API_TOKEN and KKINSTAFIX_ADMIN_KEY in release secrets')
    client = Client(token, admin, config, os.environ.get('KKINSTAFIX_LEGACY_ADMIN_KEY'))
    if args.rollback:
        state = json.loads(args.rollback.read_text())
        if 'candidate' not in state:
            raise ReleaseError('The artifact does not identify an owned deployment')
        rollback(client, state)
    else:
        deploy(client, bundle, version, build, schema, migrations,
               args.artifact, args.canary_timeout)


if __name__ == '__main__':
    try:
        main()
    except (ReleaseError, SchemaError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
