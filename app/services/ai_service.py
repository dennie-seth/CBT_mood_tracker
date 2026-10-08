from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pytz
import structlog
from anthropic import AsyncAnthropic

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOL_SCHEMAS, ToolArtifact, ToolDispatcher

log = structlog.get_logger(__name__)

_LANGUAGE_LINE = {
    "en": "Reply in English.",
    "ru": (
        "Reply in Russian. Address the user informally (ты) and use feminine "
        "grammatical forms for her (e.g. «ты спала», «ты отметила»)."
    ),
}
_MAX_TOKENS = 8000
_REFUSED = {
    "en": "Sorry, I couldn't answer that one. Could you rephrase the question?",
    "ru": "Прости, на это у меня не получилось ответить. Попробуешь переформулировать?",
}
_TOO_LONG = {
    "en": "That took too long to work out — could you ask a narrower question?",
    "ru": "Это заняло слишком много шагов — попробуй задать вопрос поуже?",
}


@dataclass
class AiAnswer:
    text: str
    artifacts: list[ToolArtifact]


class AiService:
    """Drives a tool-use loop against Anthropic's API.

    The dispatcher is created per-call and bound to the authenticated user_id —
    Haiku never receives or chooses a user_id.
    """

    def __init__(
        self,
        client: AsyncAnthropic,
        model: str,
        max_iterations: int = 8,
        effort: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._max_iterations = max_iterations
        # Only sent when configured: Claude Haiku 4.5 rejects `effort`;
        # Claude Haiku 5.5 defaults to "medium" when it's omitted.
        self._effort = effort

    async def answer(
        self,
        question: str,
        dispatcher: ToolDispatcher,
        today: date,
        *,
        target_language: str = "en",
        now: datetime | None = None,
    ) -> AiAnswer:
        tz_name = dispatcher.user_timezone
        local_now = now or datetime.now(tz=pytz.timezone(tz_name))
        user_message = (
            # Weekday + local time spelled out so the model never has to derive
            # them ("this morning", "on Tuesday") from an ISO date.
            f"Now: {today.strftime('%A')} {today.isoformat()}, "
            f"{local_now.strftime('%H:%M')} ({tz_name}).\n"
            f"{_LANGUAGE_LINE.get(target_language, _LANGUAGE_LINE['en'])}\n"
            f"<question>\n{question}\n</question>"
        )
        messages: list[dict] = [{"role": "user", "content": user_message}]

        extra: dict[str, Any] = {}
        if self._effort:
            extra["output_config"] = {"effort": self._effort}

        for _ in range(self._max_iterations):
            response = await self._client.messages.create(
                model=self._model,
                # Room for adaptive thinking (on by default on Claude Haiku 5.5,
                # and counted against max_tokens) plus a short chat reply.
                max_tokens=_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
                # System prompt + tools are identical on every call and the tool
                # loop resends the growing history, so cache the prefix. (A
                # silent no-op while it's under the model's minimum length.)
                cache_control={"type": "ephemeral"},
                **extra,
            )

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                log.warning("ai_refusal", category=getattr(details, "category", None))
                return AiAnswer(
                    text=_REFUSED.get(target_language, _REFUSED["en"]),
                    artifacts=dispatcher.artifacts,
                )

            if response.stop_reason == "tool_use":
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tu in tool_uses:
                    try:
                        result = await dispatcher.call(tu.name, dict(tu.input))
                        content = json.dumps(result, default=str)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": content,
                            }
                        )
                    except Exception as exc:  # defensive: never crash the bot on tool errors
                        log.warning("tool_call_failed", tool=tu.name, error=str(exc))
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "is_error": True,
                                "content": f"Tool error: {exc}",
                            }
                        )

                messages.append({"role": "user", "content": tool_results})
                continue

            text_parts = [b.text for b in response.content if b.type == "text"]
            return AiAnswer(text="\n".join(text_parts).strip(), artifacts=dispatcher.artifacts)

        log.warning("ai_iteration_limit", iterations=self._max_iterations)
        return AiAnswer(
            text=_TOO_LONG.get(target_language, _TOO_LONG["en"]),
            artifacts=dispatcher.artifacts,
        )
