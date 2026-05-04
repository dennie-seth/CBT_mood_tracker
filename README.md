# mood_tracker

Personal Telegram bot for **CBT (Cognitive Behavioural Therapy) self-tracking** with a Claude Haiku assistant attached. Log sleep, mood, energy, hunger, body symptoms, automatic thoughts, etc. Ask the bot to summarise, chart, or export PDF reports for any date range.

> **Private by design.** Only allow-listed Telegram accounts can use the bot. Free-text fields are encrypted at rest with `cryptography.Fernet`.

## Stack

- Python 3.12, `aiogram` 3, `SQLAlchemy` 2 async, `alembic`
- PostgreSQL 16 (dev & prod via Docker)
- `cryptography` for app-level field encryption
- Anthropic SDK — model `claude-haiku-4-5-20251001`, tool-use loop
- `pandas` + `matplotlib` for analytics, charts, PDF reports
- `pytest` + `ruff` + `mypy`

## Quickstart (local)

```sh
cp .env.example .env
# Generate a Fernet key and paste it into .env (FERNET_KEYS):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Edit `.env`:

- `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `ANTHROPIC_API_KEY` — your Anthropic key
- `ALLOWED_TELEGRAM_IDS` — your Telegram numeric ID (find via [@userinfobot](https://t.me/userinfobot)). CSV for multiple users.
- `FERNET_KEYS` — the key you generated. CSV supports rotation (first key encrypts; all keys decrypt).
- `POSTGRES_PASSWORD` — pick something
  *(`DB_URL` is computed from these — don't set it manually)*

Then:

```sh
docker compose up --build
```

The bot runs migrations on start and connects via long-polling. Send `/start` to your bot.

## Commands

The bot's `/help` lists every command with a *use-case* sentence — when to reach for it, not just what it does. Quick reference:

| Command | When to use |
|---|---|
| `/start`, `/help` | Show the full help with use cases |
| `/log` | Logging a less-common metric without remembering its specific command |
| `/mood` `/sleep` `/energy` `/hunger` `/anxiety` `/stress` `/pain` `/irritability` `/focus` | Fast in-the-moment 1–10 capture |
| `/sleephours` | Right after waking, log how long you actually slept (e.g. `7.5`) |
| `/note <text>` | Something on your mind that doesn't fit any metric (encrypted) |
| `/thought` | Catching a strong negative thought — guided CBT thought record |
| `/backfill <date> <metric> <value>` | Logging an entry for a past date |
| `/activate` | Feeling low and want a concrete mood-lifting step (Behavioral Activation) |
| `/plans` | Reviewing what plans you've committed to |
| `/done` | Just completed a planned activity — rate the actual lift |
| `/skip` | Skipping a plan, with optional reason |
| `/today`, `/week` | Today's / last 7 days' entries |
| `/chart [7d\|30d\|90d\|all]` | Spotting trends visually (PNG chart) |
| `/export [7d\|30d\|90d\|all]` | Numeric-only PDF for a private snapshot |
| `/therapist [7d\|30d\|90d\|all]` | Clinician-ready PDF: thought records, BA outcomes, notes + numeric trends |
| `/ask <question>` | Analysis the built-in views don't cover |
| `/schedule` | Inspecting current daily / weekly auto-summary settings |
| `/dailyat 21:00` | Enable an evening Haiku summary in your tz |
| `/dailyoff` | Disable daily summary |
| `/weeklyat sun 21:00` | Enable a weekly Haiku summary on this day & time |
| `/weeklyoff` | Disable weekly summary |
| `/checkins on\|off` | Proactive nudges when mood / sleep / anxiety look unusual (heuristic, opt-in, ≤ 1/day, 08:00–22:00 in your tz) |
| `/tz <IANA>` | Once on first login (e.g. `/tz Europe/Berlin`) — day boundaries depend on it |
| `/lang <en\|ru>` | Switch the bot's interface language (auto-detected from Telegram on first `/start`) |
| `/cancel` | Abort the current guided step |

## What gets tracked

Numeric (1–10): mood, energy, hunger, anxiety, stress, irritability, focus, pain, sleep quality. Plus sleep duration in hours.

Free-text (encrypted): body symptoms, thought records, activities, substances/medication, triggers, coping strategies, free-form notes.

Multiple entries on the same day combine into one day-bucket via `entry_date`. Day boundaries respect your `/tz`.

## Architecture

```
app/
  config.py         # pydantic-settings
  di.py             # process-wide DI container
  bot/
    middlewares/    # allowlist, db session, user context, container injection
    handlers/       # one router per command group
    keyboards.py    # inline keyboards
    states.py       # FSM states for multi-step flows
  domain/
    enums.py        # MetricType
    models.py       # SQLAlchemy ORM
    repositories.py # Protocols
  infrastructure/
    db.py           # async engine + sessionmaker
    crypto.py       # FernetCipher (multi-key rotation)
    repositories/   # SqlUserRepository, SqlEntryRepository, SqlScheduleRepository
    ai_client.py    # AsyncAnthropic factory
  services/
    entry_service.py   # encrypt-on-write, decrypt-on-read
    analysis_service.py # pandas DataFrames
    chart_service.py    # matplotlib PNG
    pdf_service.py      # matplotlib PdfPages
    ai_service.py       # tool-use loop
    time.py             # tz-aware date helpers
  ai/
    prompts.py     # system prompt
    tools.py       # tool schemas + dispatcher (binds user_id server-side)
alembic/           # migrations
docker/Dockerfile
docker-compose.yml
docker-compose.override.yml  # dev: source mount, exposes postgres on localhost
```

Dependencies flow inward: `handlers → services → repositories → domain`. DI is plain constructor injection (no framework). Free-text encryption is centralised in `EntryService` so handlers can't accidentally bypass it.

## Security model

| Layer | Control |
|---|---|
| Network | Long-polling only (no inbound port). Postgres `expose:` (no `ports:`) in prod compose; only dev override binds 127.0.0.1:5432. |
| AuthN | `ALLOWED_TELEGRAM_IDS` allowlist enforced by outermost middleware. |
| AuthZ | Every service call uses `user_id` derived from the authenticated update — never from message content. The Haiku agent never receives or chooses a `user_id`; the dispatcher binds it. |
| At rest | Free-text fields encrypted with Fernet. Numeric values + metric_type stay plain so analytics work without decrypts. |
| Secrets | `.env` git-ignored. Production: place `.env` 0600 root-owned; bot container runs as non-root UID 1000, read-only fs, no capabilities. |
| Logging | Structured JSON (structlog). Log level / metadata only — message text and entry payloads are NOT logged. |

### Key rotation

```env
FERNET_KEYS=<new_key>,<old_key>
```

The first key encrypts new ciphertext. All keys are tried on decrypt. Once the old key is removed from the env, only data re-encrypted with the new key remains readable — re-encrypt historical rows before deleting an old key.

## Languages

The bot ships English and Russian UI strings. On first `/start`, language is auto-detected from Telegram's `language_code` (`ru*` → Russian, otherwise English). Override at any time with `/lang en` or `/lang ru`. Strings live in [app/bot/i18n.py](app/bot/i18n.py); chart axes and PDF page titles are intentionally English-only (data labels are short and matplotlib font handling is fragile across scripts). AI responses (`/ask`, daily/weekly summaries) are produced in the user's selected language — the system prompt is told explicitly.

## Auto summaries

Each user can opt in to a daily or weekly Haiku-generated summary. Settings live in `schedule_prefs` (Postgres) and are interpreted in the user's timezone. A once-per-minute in-process tick (`SummaryScheduler`, started from `app/main.py`) scans enabled rows and invokes `SummaryService.send` for whoever's due, idempotently — `*_last_sent_date` prevents double delivery across restarts.

The empty-day case still delivers: the daily prompt asks Haiku to send a brief warm acknowledgement plus a single low-effort reflection question. Haiku replies in the user's language inferred from recent entries.

## Proactive anomaly check-ins

Opt-in (`/checkins on`) — the same scheduler tick also calls `AnomalyCheckinService.maybe_probe`. Heuristic detector ([app/services/anomaly_detector.py](app/services/anomaly_detector.py)) flags three patterns: mood ≤ 4 for 3 days in a row, sleep ≤ 5 hours for 2 nights, or anxiety ≥ 8 today. Gating (in order, all must pass): enabled, 08:00–22:00 in user tz, no probe in last 24 h, daily summary not already fired today, detector returns at least one anomaly. Templated EN/RU message with the concrete numbers — no Anthropic call per probe, so it costs nothing.

## Running tests

```sh
pip install -e ".[dev]"
pytest
```

Tests run with fake repositories — no Postgres or Anthropic API calls required.

## Production (VDS) deployment

1. Provision a small VDS (any 1 GB RAM Linux box is enough for a single user).
2. Install Docker + Docker Compose plugin.
3. Clone the repo and create `/opt/mood_tracker/.env` (root:root, mode 0600).
4. `docker compose up -d --build` from `/opt/mood_tracker`.
5. Recommended:
   - Nightly `pg_dump` cron, redirect to encrypted off-host storage:
     ```sh
     docker compose exec -T postgres pg_dump -U mood mood | age -r <pubkey> > backup.sql.age
     ```
   - Monitor container restarts; configure `journald` retention.
6. To rotate the Fernet key: prepend a new key to `FERNET_KEYS`, restart, then run a one-off re-encryption job (TODO when needed).

## What's intentionally out of scope (POC)

- Web dashboard
- Per-user encryption keys
- Reminders / scheduled nudges (could be added with APScheduler)
- HIPAA/GDPR formal compliance — this is a personal tool
- Voice / photo entry parsing

## License

MIT — see [LICENSE](LICENSE).
