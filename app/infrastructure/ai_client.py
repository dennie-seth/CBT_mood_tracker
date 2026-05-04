from __future__ import annotations

from anthropic import AsyncAnthropic


def make_anthropic_client(api_key: str) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=api_key)
