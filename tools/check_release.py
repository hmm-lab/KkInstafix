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
        changed = set(subprocess.check_output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=ROOT, text=True).splitlines())
        if any(p.startswith('cloudflare/src/') or p.startswith('cloudflare/migrations/') for p in changed):
            required = {'README.md', 'cloudflare/README.md', 'CHANGELOG.md'}
            if required - changed:
                raise SystemExit('Runtime changes require documentation: ' + ', '.join(sorted(required - changed)))
        if {'providers.py', 'cloudflare/src/config.js'} & changed and 'cloudflare/PROVIDER_REVIEW.md' not in changed:
            raise SystemExit('Provider changes require cloudflare/PROVIDER_REVIEW.md')
    subprocess.run(['python', 'cloudflare/generate-config.py'], cwd=ROOT, check=True)
    subprocess.run(['git', 'diff', '--exit-code', '--', 'cloudflare/src/config.js', 'cloudflare/schema.sql'], cwd=ROOT, check=True)
    print(f'Release {version}: documentation and generated configuration match')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    check(parser.parse_args().base)
