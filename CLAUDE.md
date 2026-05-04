# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

Personal Telegram bot for **CBT (Cognitive Behavioural Therapy) self-tracking** with a Claude Haiku assistant attached. The bot logs structured numeric metrics (mood, sleep, energy, …) and free-text records (notes, thought records, symptoms). A Haiku 4.5 tool-use loop answers questions, generates PNG charts, and produces multi-page PDF reports over arbitrary date ranges.

Single-user / small-circle; **strictly private** — only allow-listed Telegram IDs may use it; free-text fields are encrypted at rest with `cryptography.Fernet`.

POC runs locally; production target is a single VDS via the existing `docker compose` stack.

## Stack

- Python 3.12, `aiogram` 3, `SQLAlchemy` 2 async, `alembic`, PostgreSQL 16
- `cryptography` (Fernet, multi-key rotation)
- Anthropic SDK — model `claude-haiku-4-5-20251001`
- `pandas` + `matplotlib` (PNG charts and `PdfPages` reports — no extra PDF lib)
- `pytest` + `pytest-asyncio`, `ruff`, `mypy`

## Repo layout

```
app/
  config.py · di.py · main.py · logging_setup.py
  ai/                    prompts + Haiku tool schemas + dispatcher
  bot/
    handlers/            one router per command group
    middlewares/         auth, db, user_ctx, context (DI injection)
    keyboards.py · states.py
  domain/                MetricType, ORM models, repository protocols
  infrastructure/        engine, FernetCipher, repo implementations, AI client
  services/              entry, analysis, chart, pdf, ai, time helpers
alembic/                 env.py + versioned migrations
tests/unit/              fast, no Postgres, no Anthropic (fake repos / mocks)
docker/Dockerfile        multi-stage, non-root UID 1000, read-only fs
docker-compose.yml       bot + postgres, no host port for postgres
docker-compose.override.yml  dev: source mount, exposes pg on 127.0.0.1
```

Dependencies flow inward: **handlers → services → repositories → domain**. DI is constructor injection wired in `app/di.py` — no DI framework. Per-request services are built inside handlers from the `AsyncSession` provided by `DbSessionMiddleware`.

## How to work in this repo

### TDD is the workflow

Write the failing test first, watch it fail, then implement.

- New feature → start with a test in `tests/unit/`. Use fake repositories (see `tests/unit/test_entry_service.py:FakeEntryRepo`) — don't reach for Postgres unless the test genuinely needs it.
- Bug → reproduce with a failing test, then fix.
- Refactor → confirm coverage exists; if not, add tests first.
- Don't bundle multiple untested changes in one commit.

### Running things

```sh
# Install dev deps once
pip install -e ".[dev]"

# Tests (fast, no docker)
pytest

# Lint / typecheck
ruff check .
mypy app

# Full local run
docker compose up --build
```

### Style and architecture rules

- **Single chokepoint for crypto**: all encryption/decryption goes through `EntryService`. Handlers must never touch `value_text_encrypted` directly. Free-text in `metadata` is encrypted by convention — keys ending in `_text` get encrypted automatically.
- **AI never sees user_id**: the `ToolDispatcher` in `app/ai/tools.py` binds `user_id` server-side. Tool schemas exposed to Haiku do NOT contain a `user_id` parameter. Don't add one.
- **Allowlist is the outermost middleware**. Don't add handlers that bypass it. Don't put auth checks inside handlers.
- **Logs never contain message text or entry payloads** — only `metric_type`, ids, and counts. `structlog` is configured in `app/logging_setup.py`; use it (`structlog.get_logger(__name__)`) rather than the stdlib logger.
- **`User.timezone` defines day boundaries**. When computing `entry_date`, always go through `EntryService.create` (which converts UTC → user tz → date) or `app/services/time.py` helpers. Don't use `datetime.now().date()`.
- **FSM state is persistent**: aiogram's storage is `PgFsmStorage` ([app/infrastructure/fsm_storage.py](app/infrastructure/fsm_storage.py)), backed by the `fsm_state` Postgres table. The `data` blob is encrypted with the same `FernetCipher` as entries — so handlers can put free-text into `state.update_data(...)` mid-flow without leaking plaintext to the DB. Stale rows (>7 days) are pruned opportunistically on each write; no scheduler.
- **Layered, KISS**: don't introduce abstractions until two concrete needs exist. The `repositories.py` Protocols exist because both production code (Postgres) and tests (fakes) implement them — that's the bar.

### Adding a new metric

1. Add the value to `MetricType` in `app/domain/enums.py` and to `NUMERIC_METRICS` or `TEXT_METRICS`.
2. Add a label to `METRIC_LABELS`.
3. If it's a numeric metric, optionally add a quick command in `app/bot/handlers/quick.py` (`QUICK_COMMANDS` dict).
4. Write a test that the entry round-trips through `EntryService` and shows up in `daily_summary` (numeric) or in `list_range` decrypted (text).
5. **No migration needed** — `metric_type` is a free-form `String(32)` column.

### Adding a new bot command

1. Write a test in `tests/unit/` that exercises the relevant service (handlers themselves are thin; the logic lives in services).
2. Create or extend a router in `app/bot/handlers/`.
3. Register it in `app/bot/handlers/__init__.py:register_all`.
4. Update the help text in `app/bot/handlers/start.py:HELP_TEXT` and the table in `README.md`.

### Adding a new AI tool

1. Test the underlying service method first.
2. Add a schema to `TOOL_SCHEMAS` in `app/ai/tools.py` — never include a `user_id` parameter.
3. Add a `_handler` method to `ToolDispatcher` and dispatch it in `call(...)`.
4. If the tool returns a binary artifact (PNG/PDF), append a `ToolArtifact` to `self.artifacts` and return a small JSON ack — the host (`AskHandler`) uploads the file.
5. Update `app/ai/prompts.py` with one line describing the new capability.

### Database migrations

```sh
docker compose run --rm bot alembic revision --autogenerate -m "what changed"
docker compose run --rm bot alembic upgrade head
```

Production container runs `alembic upgrade head` automatically via `docker/entrypoint.sh`.

## Security checklist for any change

- [ ] No new code path bypasses `AllowlistMiddleware`.
- [ ] No handler reads/writes `value_text_encrypted` directly — always via `EntryService`.
- [ ] No new tool schema exposes `user_id`.
- [ ] Logs in the new code don't include message text, note bodies, or thought-record contents.
- [ ] If a new env variable holds a secret, document it in `.env.example` with a placeholder (never a real value) and add it to `Settings`.
- [ ] If a Postgres port is added to compose, it's bound to `127.0.0.1` only and only in `docker-compose.override.yml`.

## Things to leave alone unless asked

- Don't switch the bot framework, ORM, or AI provider.
- Don't add a web dashboard, voice/photo parsing, or APScheduler reminders — explicitly out of scope for the POC (see `README.md`).
- Don't replace Fernet with a different cipher — multi-key rotation already works.

## Reference paths

- Plan: `C:\Users\denni\.claude\plans\purring-knitting-sundae.md`
- Memory: `C:\Users\denni\.claude\projects\f--PetProjects-mood-tracker\memory\`
