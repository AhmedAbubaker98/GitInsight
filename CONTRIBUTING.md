# Contributing to GitInsight

Thanks for your interest in contributing.

This document explains how to set up your environment, how code quality is enforced, how to run tests, and how to submit pull requests.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### 1) Fork and Clone

1. Fork this repository on GitHub.
2. Clone your fork locally.
3. Create a feature branch from `main`.

Example:

```bash
git clone https://github.com/<your-user>/GitInsight.git
cd GitInsight
git checkout -b feature/short-description
```

### 2) Configure Environment Variables

The app expects an `.env` file in the `app` directory.

```bash
cd app
cp .env.example .env
```

Then fill in required values in `.env`:

- `SESSION_SECRET`
- `MY_DATABASE_URL`
- `REDIS_URL`
- `AI_ANALYZER_MY_GOOGLE_API_KEY`

Optional for GitHub OAuth/private repo flow:

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`

### 3) Install Dependencies (Local, Optional)

You can run with Docker only, but for local development you can install service dependencies in a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# Linux/macOS
# source .venv/bin/activate

pip install -r app/api_service/requirements.txt
pip install -r app/repo_processor_service/requirements.txt
pip install -r app/ai_analyzer_service/requirements.txt
```

### 4) Run the Project

From `app`:

```bash
docker compose up --build
```

Then open `http://localhost:8000`.

## Code Style Standards

These standards apply to all contributions.

- Follow PEP 8 and keep code readable over clever.
- Use explicit type hints for new or modified public functions.
- Add concise docstrings for modules, classes, and non-trivial functions.
- Keep functions focused and small when possible.
- Prefer clear names over short names.
- Do not introduce unrelated refactors in the same PR.

### Formatting

Use Black formatting conventions (line length 88).

```bash
pip install black
black app
```

### Linting

Use Ruff for linting.

```bash
pip install ruff
ruff check app
```

If lint output indicates fixable issues, run:

```bash
ruff check app --fix
```

## Testing Requirements

Every bug fix or feature should include tests for the changed behavior.

Minimum expectations:

- Add or update tests for the code paths you changed.
- Cover both success and failure cases for business logic.
- Avoid tests that rely on external network services.
- Keep tests deterministic.

If you add new endpoints, include API-level tests.
If you change database behavior, include DB-related tests.

## Running Tests Locally

Install test tooling:

```bash
pip install pytest pytest-asyncio httpx
```

Run tests:

```bash
pytest -q
```

If no tests are present yet for your area, at least run a smoke check before opening a PR:

```bash
python -m compileall app
```

## Pull Request Process

1. Ensure your branch is up to date with `main`.
2. Keep PRs scoped to a single logical change.
3. Run formatting, linting, and tests locally.
4. Update docs when behavior or setup changes.
5. Open a PR with a clear title and description.

Please include in your PR description:

- What changed
- Why it changed
- How it was tested
- Any follow-up work

### PR Checklist

- [ ] Code is formatted
- [ ] Lint checks pass
- [ ] Tests added/updated where needed
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No secrets or credentials committed

## Commit Message Guidance

Use clear, imperative commit messages.

Examples:

- `fix: handle Redis connection failure in worker startup`
- `feat: add repository parser size guard`
- `docs: improve local setup instructions`

## Need Help?

If you are unsure about design direction for a larger change, open an issue first so maintainers can align on scope before implementation.
