#!/bin/sh
set -eu

# Run database migrations to head before starting the bot.
alembic upgrade head

exec "$@"
