# Contributing

## Setup
Requires Python >= 3.11. No dependencies to install (stdlib-only).
```bash
python3 -m app.main      # run
python3 -m pytest -q     # test (pytest is the only dev dependency)
```

## Workflow
1. Open an issue describing the change; link it in your PR.
2. Branch: `feat/<short-name>` or `fix/<short-name>`.
3. Keep the stdlib-only constraint: no new runtime dependencies without discussion — if you must add one, update `requirements.txt` and justify it in the PR.
4. Add tests for `stats.py`, `detector.py`, and any new API route. Coverage gate: 70% on core modules.
5. Frontend changes must work with no build step (static HTML/CSS/JS in `app/static/`).
6. Update docs (`docs/`) when behavior changes.

## Code style
- `snake_case`, type hints on public functions, docstrings on modules.
- No `innerHTML` with user data; keep SSRF guards intact (see `docs/architecture.md`).
