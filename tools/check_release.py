"""Check shared Worker version, release notes and generated configuration in CI."""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(base=None):
    version = re.search(r"VERSION='([^']+)'", (ROOT / 'cloudflare/src/version.js').read_text())[1]
    for name in ['README.md', 'cloudflare/README.md', 'CHANGELOG.md']:
        if version not in (ROOT / name).read_text():
            raise SystemExit(f'{name} must document Worker {version}')
    if f'## [{version}] - ' not in (ROOT / 'CHANGELOG.md').read_text():
        raise SystemExit('A dated release changelog entry is required')
    if base:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--verify', '--end-of-options', f'{base}^{{commit}}'], cwd=ROOT, text=True
        ).strip()
        changed = set(subprocess.check_output(
            ['git', 'diff', '--name-only', commit, 'HEAD', '--'], cwd=ROOT, text=True
        ).splitlines())
        runtime_paths = {'cloudflare/deployment.json', 'cloudflare/generate-config.py',
                         'tools/d1_release.py', 'tools/release_cloudflare.py'}
        if runtime_paths & changed or any(p.startswith(('cloudflare/src/', 'cloudflare/migrations/')) for p in changed):
            required = {'README.md', 'cloudflare/README.md', 'CHANGELOG.md'}
            if required - changed:
                raise SystemExit('Runtime changes require documentation: ' + ', '.join(sorted(required - changed)))
        provider_paths = {'providers.py', 'cloudflare/src/config.js', 'cloudflare/src/health.js',
                          'cloudflare/src/provider-policy.js'}
        if provider_paths & changed and 'cloudflare/PROVIDER_REVIEW.md' not in changed:
            raise SystemExit('Provider changes require cloudflare/PROVIDER_REVIEW.md')
    subprocess.run(['python', 'cloudflare/generate-config.py', '--check'], cwd=ROOT, check=True)
    print(f'Release {version}: documentation and generated configuration match')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    check(parser.parse_args().base)
