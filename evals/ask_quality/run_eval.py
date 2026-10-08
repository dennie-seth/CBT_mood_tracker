"""Run the /ask eval for one variant.

    python evals/ask_quality/run_eval.py --variant v1 --model claude-haiku-4-5-20251001
    python evals/ask_quality/run_eval.py --variant baseline --model ... --app-root <main checkout>

Calls the app's real entry point (AiService.answer + ToolDispatcher +
EntryService/AnalysisService/Chart/PDF services) against a fresh in-memory
fictional journal per trial; only Postgres is swapped out. --app-root lets
the baseline run the previous app version unchanged.

Writes .claude/hillclimb/ask_quality/<variant>/{results.jsonl, traces/, errors.jsonl}.
Resume is idempotent per (case, rep). Infra failures (API errors after SDK
retries, timeouts, served-model mismatch, judge failures) go to errors.jsonl,
never results.jsonl. Rows that hit max_tokens get status "truncated".
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytz

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FLOW = REPO / ".claude" / "hillclimb" / "ask_quality"
HARNESS_FILES = ("run_eval.py", "judge.py", "fixture.py", "cases.py", "memory_repo.py")
SHA_FILE = FLOW / "harness.sha"


def _harness_sha() -> str:
    h = hashlib.sha256()
    for name in HARNESS_FILES:
        h.update(name.encode())
        h.update((HERE / name).read_bytes())
    return h.hexdigest()


def _check_harness(approve: bool) -> None:
    sha = _harness_sha()
    FLOW.mkdir(parents=True, exist_ok=True)
    if approve:
        SHA_FILE.write_text(sha + "\n", encoding="utf-8")
        print(f"harness approved: {sha[:12]}")
        return
    if not SHA_FILE.exists() or SHA_FILE.read_text(encoding="utf-8").strip() != sha:
        print("Harness files changed or not yet approved. Review evals/ask_quality/ and re-run "
              "with --approve-harness (the repo owner's decision).", file=sys.stderr)
        sys.exit(2)


def _load_api_key(env_file: Path) -> str:
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit(f"ANTHROPIC_API_KEY not found in {env_file}")


class RecordingClient:
    """Wraps AsyncAnthropic so every call's request/response is recorded and
    the served model is asserted."""

    def __init__(self, inner: Any, expected_model: str) -> None:
        self._inner = inner
        self._expected = expected_model
        self.calls: list[tuple[dict[str, Any], Any, float]] = []
        self.messages = self

    async def create(self, **kwargs: Any) -> Any:
        snapshot = dict(kwargs)
        snapshot["messages"] = list(kwargs["messages"])
        t0 = time.perf_counter()
        response = await self._inner.messages.create(**kwargs)
        self.calls.append((snapshot, response, time.perf_counter() - t0))
        if not str(response.model).startswith(self._expected.split("-2025")[0]):
            raise ModelMismatch(f"asked {self._expected}, served {response.model}")
        return response


class ModelMismatch(RuntimeError):
    pass


def _usage(calls: list[tuple[dict[str, Any], Any, float]]) -> dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    for _, r, _ in calls:
        for k in total:
            total[k] += int(getattr(r.usage, k, 0) or 0)
    return total


def _block_dict(b: Any) -> dict[str, Any]:
    return b if isinstance(b, dict) else b.model_dump()


def _trace(calls: list[tuple[dict[str, Any], Any, float]]) -> list[dict[str, Any]]:
    if not calls:
        return []
    req, final, _ = calls[-1]
    turns: list[dict[str, Any]] = [{"role": "system", "content": req.get("system", "")}]
    history = list(req["messages"]) + [{"role": "assistant", "content": final.content}]
    for msg in history:
        content = msg["content"]
        if isinstance(content, str):
            turns.append({"role": msg["role"], "content": content})
            continue
        thinking = ""
        for raw in content:
            b = _block_dict(raw)
            kind = b.get("type")
            if kind == "thinking":
                thinking += b.get("thinking") or "(thinking omitted)"
            elif kind == "text":
                turn = {"role": "assistant", "content": b["text"]}
                if thinking:
                    turn["thinking"], thinking = thinking, ""
                turns.append(turn)
            elif kind == "tool_use":
                turn = {"role": "tool_call", "name": b["name"],
                        "content": json.dumps(b["input"], indent=2, ensure_ascii=False)}
                if thinking:
                    turn["thinking"], thinking = thinking, ""
                turns.append(turn)
            elif kind == "tool_result":
                turns.append({"role": "tool_result", "content": str(b.get("content", ""))})
    return turns


def _tools_called(calls: list[tuple[dict[str, Any], Any, float]]) -> list[str]:
    names = []
    for _, r, _ in calls:
        for b in r.content:
            if getattr(b, "type", None) == "tool_use":
                names.append(b.name)
    return names


async def run_case(case: Any, rep: int, args: argparse.Namespace, judge_client: Any,
                   api_client: Any) -> dict[str, Any]:
    from cryptography.fernet import Fernet
    from fixture import TZ, build
    from judge import judge, language_ok, plain_text_ok
    from memory_repo import MemoryEntryRepo

    from app.ai.tools import ToolDispatcher
    from app.domain.models import User
    from app.infrastructure.crypto import FernetCipher
    from app.services.ai_service import AiService
    from app.services.analysis_service import AnalysisService
    from app.services.chart_service import ChartService
    from app.services.entry_service import EntryService
    from app.services.migraine_service import MigraineService
    from app.services.pdf_service import PdfService

    tz = pytz.timezone(TZ)
    now = datetime.now(tz=tz)
    today = now.date()
    user = User(telegram_id=1, display_name="eval", timezone=TZ, language=case.lang)
    user.id = 1
    repo = MemoryEntryRepo()
    es = EntryService(repo, FernetCipher([Fernet.generate_key().decode()]))
    fx = await build(es, MigraineService, user, today)
    question, checks = case.render(fx.facts)

    client = RecordingClient(api_client, args.model)
    kwargs: dict[str, Any] = {"client": client, "model": args.model, "max_iterations": 8}
    if args.effort and "effort" in inspect.signature(AiService.__init__).parameters:
        kwargs["effort"] = args.effort
    svc = AiService(**kwargs)
    dispatcher = ToolDispatcher(
        user_id=user.id, user_timezone=TZ, entry_service=es,
        analysis_service=AnalysisService(repo), chart_service=ChartService(),
        pdf_service=PdfService(),
    )
    answer_kwargs: dict[str, Any] = {"target_language": case.lang}
    if "now" in inspect.signature(svc.answer).parameters:
        answer_kwargs["now"] = now
    t0 = time.perf_counter()
    answer = await svc.answer(question, dispatcher, today, **answer_kwargs)
    latency = time.perf_counter() - t0
    text = answer.text
    final_stop = client.calls[-1][1].stop_reason if client.calls else None

    row: dict[str, Any] = {
        "prompt_id": case.id, "rep": rep, "prompt": question, "tags": list(case.tags),
        "model": str(client.calls[-1][1].model) if client.calls else args.model,
        "usage": _usage(client.calls), "model_calls": len(client.calls),
        "tool_calls": len(_tools_called(client.calls)), "latency_s": round(latency, 2),
        "stop_reason": final_stop,
        "status": "truncated" if final_stop == "max_tokens" else "ok",
        "answer": text, "meta": {"effort": args.effort, "today": str(today)},
    }
    fmt = plain_text_ok(text)
    lang = language_ok(text, case.lang)
    tool_ok = case.needs_tool is None or case.needs_tool in _tools_called(client.calls)
    j = await judge(judge_client, journal=fx.lines, today=f"{fx.facts['today_wd']} {today}",
                    question=question, lang=case.lang, checks=checks, answer=text)
    passed = sum(j.passes)
    row["grade"] = {
        "pass": float(fmt and lang and tool_ok and all(j.passes)),
        "checks": round(passed / len(checks), 3),
        "format": float(fmt), "language": float(lang),
    }
    row["explanation"] = {
        "pass": " | ".join(f"{'✓' if p else '✗'} {c} — {r}"
                           for c, p, r in zip(checks, j.passes, j.reasons, strict=True))
        + ("" if tool_ok else f" | ✗ {case.needs_tool} was not called"),
    }
    row["judge_model"], row["judge_usage"] = j.model, j.usage
    row["_trace"] = _trace(client.calls)
    return row


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--effort", default=None)
    p.add_argument("--app-root", default=str(REPO))
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--timeout-s", type=float, default=300)
    p.add_argument("--env-file", default=str(REPO / ".env"))
    p.add_argument("--approve-harness", action="store_true")
    args = p.parse_args()

    if args.variant != "baseline" and not (args.variant.startswith("v") and args.variant[1:].isdigit()):
        raise SystemExit("--variant must be 'baseline' or v<N>")
    _check_harness(args.approve_harness)
    sys.path.insert(0, str(Path(args.app_root).resolve()))
    sys.path.insert(1, str(HERE))

    from anthropic import AsyncAnthropic
    from cases import CASES

    api_client = AsyncAnthropic(api_key=_load_api_key(Path(args.env_file)), max_retries=4)
    out = FLOW / args.variant
    (out / "traces").mkdir(parents=True, exist_ok=True)
    results_path, errors_path = out / "results.jsonl", out / "errors.jsonl"
    done = set()
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["prompt_id"], r["rep"]))

    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    jobs = [(c, rep) for c in CASES if not wanted or c.id in wanted
            for rep in range(args.reps) if (c.id, rep) not in done]
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    t_start = time.perf_counter()

    async def one(case: Any, rep: int) -> None:
        async with sem:
            try:
                row = await asyncio.wait_for(
                    run_case(case, rep, args, api_client, api_client), args.timeout_s
                )
            except Exception as exc:  # recorded, never scored
                kind = ("timeout" if isinstance(exc, TimeoutError)
                        else "model_mismatch" if type(exc).__name__ == "ModelMismatch"
                        else "judge" if type(exc).__name__ == "JudgeError"
                        else "harness_or_serving")
                async with lock:
                    with errors_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"prompt_id": case.id, "rep": rep, "class": kind,
                                            "error": f"{type(exc).__name__}: {exc}"[:500]}) + "\n")
                print(f"  ERROR {case.id} rep{rep}: {kind}: {exc}"[:200])
                return
            trace = row.pop("_trace")
            async with lock:
                (out / "traces" / f"{case.id}_rep{rep}.json").write_text(
                    json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
                with results_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  {case.id} rep{rep}: pass={row['grade']['pass']:.0f} "
                  f"checks={row['grade']['checks']:.2f} fmt={row['grade']['format']:.0f}")

    print(f"{args.variant}: {len(jobs)} trials on {args.model} (effort={args.effort})")
    await asyncio.gather(*(one(c, r) for c, r in jobs))
    print(f"done in {time.perf_counter() - t_start:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
