# Python backend service

FastAPI backend for EVE Healthcare diagnostic bookings + simulated payments. See `python-backend/README.md` for run instructions and API examples; `python-backend/docs/` is the Obsidian vault.

## Stack

- FastAPI + SQLAlchemy 2.0 + PostgreSQL (psycopg 3), PyJWT, bcrypt
- Tests: pytest + httpx (SQLite temp file, 52 tests)
- Docker: `postgres:16-alpine` + `python:3.12-slim`

## Commands

Run from `python-backend/`:

```bash
.venv\Scripts\python -m pytest tests -q      # tests
.venv\Scripts\uvicorn app.main:app --reload  # dev server
docker compose up --build                    # full stack
```

## Conventions

- Every API response uses the shared envelope — see `app/http.py` (`ok`/`fail`) and `app/errors.py` (error codes). Never hand-build responses.
- Money is stored as integer paise, exposed as rupees.
- All timestamps naive UTC.
- No comments unless marking a deliberate simplification with `# ponytail:`.
