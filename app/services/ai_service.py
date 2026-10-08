from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

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
    ) -> None:
        self._client = client
        self._model = model
        self._max_iterations = max_iterations

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

        for _ in range(self._max_iterations):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
                # System prompt + tools are identical on every call and the tool
                # loop resends the growing history, so cache the prefix. (A
                # silent no-op while it's under the model's minimum length.)
                cache_control={"type": "ephemeral"},
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
