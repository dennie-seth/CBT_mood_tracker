from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytz

from app.domain.enums import NUMERIC_METRICS, TEXT_METRICS, MetricType
from app.domain.models import Entry, User
from app.domain.repositories import EntryRepository
from app.infrastructure.crypto import FernetCipher


@dataclass(frozen=True, slots=True)
class EntryDTO:
    id: int
    recorded_at: datetime
    entry_date: date
    metric_type: MetricType
    value_numeric: float | None
    value_text: str | None
    tags: list[str] | None
    extra: dict[str, Any] | None


class EntryService:
    """Encrypts free text on write, decrypts on read; numeric stays plain."""

    def __init__(self, repo: EntryRepository, cipher: FernetCipher) -> None:
        self._repo = repo
        self._cipher = cipher

    async def create(
        self,
        user: User,
        metric_type: MetricType,
        *,
        value_numeric: float | None = None,
        value_text: str | None = None,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        recorded_at: datetime | None = None,
    ) -> EntryDTO:
        if metric_type in NUMERIC_METRICS and value_numeric is None:
            raise ValueError(f"{metric_type} requires a numeric value")
        if metric_type in TEXT_METRICS and not (value_text or extra):
            raise ValueError(f"{metric_type} requires text content")

        ts = recorded_at or datetime.now(tz=pytz.utc)
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts)
        user_tz = pytz.timezone(user.timezone)
        bucket = ts.astimezone(user_tz).date()

        encrypted_text = self._cipher.encrypt(value_text) if value_text else None
        # Encrypt any free-text values nested in metadata too.
        safe_extra = self._encrypt_extra(extra) if extra else None

        entry = Entry(
            user_id=user.id,
            recorded_at=ts,
            entry_date=bucket,
            metric_type=metric_type.value,
            value_numeric=Decimal(str(value_numeric)) if value_numeric is not None else None,
            value_text_encrypted=encrypted_text,
            tags=tags,
            extra=safe_extra,
        )
        saved = await self._repo.add(entry)
        return self._to_dto(saved)

    async def list_range(
        self,
        user_id: int,
        start: date,
        end: date,
        metric_types: list[MetricType] | None = None,
    ) -> list[EntryDTO]:
        names = [m.value for m in metric_types] if metric_types else None
        rows = await self._repo.list_range(user_id, start, end, names)
        return [self._to_dto(r) for r in rows]

    def _to_dto(self, e: Entry) -> EntryDTO:
        text = self._cipher.decrypt(e.value_text_encrypted) if e.value_text_encrypted else None
        extra = self._decrypt_extra(e.extra) if e.extra else None
        return EntryDTO(
            id=e.id,
            recorded_at=e.recorded_at,
            entry_date=e.entry_date,
            metric_type=MetricType(e.metric_type),
            value_numeric=float(e.value_numeric) if e.value_numeric is not None else None,
            value_text=text,
            tags=list(e.tags) if e.tags else None,
            extra=extra,
        )

    # Convention: keys ending in "_text" inside metadata are sensitive.
    def _encrypt_extra(self, extra: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in extra.items():
            if k.endswith("_text") and isinstance(v, str):
                # Store ciphertext as base64-printable so it lives in JSONB.
                out[k] = {"__enc__": True, "v": self._cipher.encrypt(v).decode("ascii")}
            else:
                out[k] = v
        return out

    def _decrypt_extra(self, extra: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in extra.items():
            if isinstance(v, dict) and v.get("__enc__"):
                out[k] = self._cipher.decrypt(v["v"].encode("ascii"))
            else:
                out[k] = v
        return out
