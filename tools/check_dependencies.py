#!/usr/bin/env python3
"""Check for outdated packages in the current environment."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run pip list --outdated and display results."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running pip list: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        outdated = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Error parsing pip output: {e}", file=sys.stderr)
        sys.exit(1)

    if not outdated:
        print("All packages are up to date.")
        return

    print("Outdated packages:")
    for package in outdated:
        print(f"{package['name']}: {package['version']} -> {package['latest_version']}")


if __name__ == "__main__":
    main()