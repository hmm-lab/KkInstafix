# Contributing to KkInstafix

Thank you for considering contributing to KkInstafix! This document outlines the process for contributing to this project.

## Development Setup

1. Fork the repository
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/kkinstafix.git
   cd kkinstafix
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Running Tests

To run the test suite:
```bash
pytest
```

To run tests with coverage:
```bash
pytest --cov=bot --cov=providers --cov=database
```

To run a specific test file:
```bash
pytest test_bot.py
pytest test_handlers.py
```

## Making Changes

### Adding New Providers

Providers are defined in `providers.py`. To add a new provider:

1. Add the provider to the `PROVIDERS` dictionary in `providers.py`
2. Follow the existing format:
   ```python
   "newplatform": {
       "options": {
           "providerkey": "providerdomain.com",
           # ... other options
       },
       "domains": ["originaldomain.com", "www.originaldomain.com"],
       # Optional: noauth_embed mapping for privacy frontends
       "noauth_embed": {
           "providerkey": "embedproviderkey"
       }
   }
   ```
3. Add any necessary tracking parameters to the appropriate tracking dictionaries
4. Add emoji to `PLATFORM_EMOJI` dictionary
5. Add sample URL to `SAMPLE_URLS` dictionary for health checking
6. Add tests for the new provider in `test_bot.py`

### Running Pre-commit Hooks

Pre-commit hooks run automatically on commit, but you can run them manually:
```bash
pre-commit run --all-files
```

### Code Style

- Follow PEP 8 for Python code
- Use type hints for all function parameters and return values
- Keep lines to a maximum of 88 characters when possible
- Write clear, descriptive commit messages

## Making a Release

To create a new release:

1. Ensure all changes are committed and the working directory is clean
2. Run the version bump script:
   ```bash
   python bump_version.py --bump patch   # or --bump minor / --bump major
   # or specify exact version: python bump_version.py --version 1.55.0
   ```
3. The script will update:
   - `bot.py`: `__version__`
   - `README.md`: version badge
   - `CHANGELOG.md`: new version section (fill in the changes)
4. Review the changes and fill in the CHANGELOG section with details
5. Commit the changes:
   ```bash
   git add bot.py README.md CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   ```
6. Create and push the tag:
   ```bash
   git tag vX.Y.Z
   git push && git push --tags
   ```
7. The CI/CD pipeline will automatically run tests on the tag

## Reporting Issues

Please use the GitHub issue tracker to report bugs or request features. Include:
- Clear description of the issue
- Steps to reproduce (if applicable)
- Expected vs actual behavior
- Relevant logs or screenshots

## License

By contributing to KkInstafix, you agree that your contributions will be licensed under the project's license.

Thank you for your contribution!