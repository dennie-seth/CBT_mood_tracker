FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml ./
RUN pip install --upgrade pip build \
    && pip wheel --no-deps --wheel-dir /wheels . \
    && pip wheel --wheel-dir /wheels \
        "aiogram>=3.4,<4" \
        "sqlalchemy[asyncio]>=2.0,<3" \
        "asyncpg>=0.29" \
        "alembic>=1.13" \
        "pydantic-settings>=2.2" \
        "cryptography>=42.0" \
        "anthropic>=0.40" \
        "pandas>=2.2" \
        "matplotlib>=3.8" \
        "pytz>=2024.1" \
        "structlog>=24.1"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --home-dir /home/app app

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels

COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
