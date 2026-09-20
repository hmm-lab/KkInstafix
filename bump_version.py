#!/usr/bin/env python3
"""
bump_version.py - Script to bump the version of KkInstafix.

Usage:
    python bump_version.py [--version VERSION] [--bump {major,minor,patch}] [--dry-run]

If --version is provided, it sets the exact version.
Otherwise, it bumps the version according to --bump (default: patch).
Use --dry-run to see what would be changed without modifying files.
"""

import re
import sys
import argparse
from datetime import date
from pathlib import Path

def get_current_version():
    """Extract current version from bot.py."""
    bot_path = Path("bot.py")
    content = bot_path.read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', content)
    if not match:
        raise RuntimeError("Could not find __version__ in bot.py")
    return match.group(1)

def bump_version(version, bump_type):
    """Bump version according to bump_type."""
    major, minor, patch = map(int, version.split("."))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"

def update_bot_py(new_version, dry_run=False):
    """Update __version__ in bot.py."""
    bot_path = Path("bot.py")
    content = bot_path.read_text(encoding="utf-8")
    updated = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content)
    if dry_run:
        print(f"[DRY RUN] Would update bot.py: set __version__ to {new_version}")
        return
    bot_path.write_text(updated, encoding="utf-8")
    print(f"Updated bot.py: set __version__ to {new_version}")

def update_readme_md(new_version, dry_run=False):
    """Update version badge in README.md."""
    readme_path = Path("README.md")
    content = readme_path.read_text(encoding="utf-8")
    # Match the line: "Current version: **1.54.0** — see [CHANGELOG.md](CHANGELOG.md) for release history."
    updated = re.sub(
        r'Current version: \*\*[^*]+\*\*',
        f'Current version: **{new_version}**',
        content
    )
    if dry_run:
        print(f"[DRY RUN] Would update README.md: set version badge to {new_version}")
        return
    readme_path.write_text(updated, encoding="utf-8")
    print(f"Updated README.md: set version badge to {new_version}")

def update_changelog_md(new_version, dry_run=False):
    """Insert a new version section into CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    content = changelog_path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    new_section = f"""## [{new_version}] - {today}

### Changed
-

"""
    # Insert after the first line (which is "# Changelog") and the blank line?
    # We'll insert after the first two lines: "# Changelog" and blank line.
    lines = content.splitlines(keepends=True)
    if len(lines) >= 2 and lines[0].strip() == "# Changelog" and lines[1].strip() == "":
        # Insert after line 1 (index 1)
        lines.insert(2, new_section)
    else:
        # Fallback: insert at the beginning after the first line.
        lines.insert(1, new_section)
    new_content = "".join(lines)
    if dry_run:
        print(f"[DRY RUN] Would update CHANGELOG.md: add new section for {new_version}")
        return
    changelog_path.write_text(new_content, encoding="utf-8")
    print(f"Updated CHANGELOG.md: added new section for {new_version}")

def main():
    parser = argparse.ArgumentParser(description="Bump version of KkInstafix.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--version", help="Set exact version (e.g., 1.55.0)")
    group.add_argument("--bump", choices=["major", "minor", "patch"], default="patch",
                       help="Bump version (default: patch)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be changed without modifying files")
    args = parser.parse_args()

    current = get_current_version()
    if args.version:
        new_version = args.version
        # Validate format
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            sys.exit("Error: Version must be in format X.Y.Z")
    else:
        new_version = bump_version(current, args.bump)

    print(f"Current version: {current}")
    print(f"New version: {new_version}")

    update_bot_py(new_version, args.dry_run)
    update_readme_md(new_version, args.dry_run)
    update_changelog_md(new_version, args.dry_run)

    if not args.dry_run:
        print("\nNext steps:")
        print("1. Fill in the changes in the new section of CHANGELOG.md")
        print("2. Commit the changes: git add bot.py README.md CHANGELOG.md")
        print("3. Commit and tag: git commit -m \"Release v{new_version}\" && git tag v{new_version}")
        print("4. Push: git push && git push --tags")

if __name__ == "__main__":
    main()