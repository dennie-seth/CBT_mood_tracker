"""Summarise every variant: pass rate with 95% CI, paired delta vs baseline,
sub-metrics, and cost per answer (model) and per grade (judge) computed from
recorded usage × list price. Prints markdown; --out writes it to a file.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

FLOW = Path(__file__).resolve().parents[2] / ".claude" / "hillclimb" / "ask_quality"
# $/MTok (input, output) — first-party list prices; cache write 1.25x, read 0.1x input.
PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}
LABELS = {
    "baseline": "Haiku 4.5 + old prompt (production today)",
    "v1": "Haiku 4.5 + new prompt",
    "v2": "Haiku 5.5 low + new prompt",
    "v3": "Haiku 5.5 medium + new prompt + tool fixes",
    "v4": "Haiku 5.5 low + new prompt + tool fixes",
}


def _price(model: str) -> tuple[float, float]:
    for prefix, p in PRICES.items():
        if model.startswith(prefix):
            return p
    raise KeyError(f"no price for {model}")


def cost(model: str, usage: dict[str, int]) -> float:
    pin, pout = _price(model)
    return (usage.get("input_tokens", 0) * pin
            + usage.get("cache_creation_input_tokens", 0) * pin * 1.25
            + usage.get("cache_read_input_tokens", 0) * pin * 0.1
            + usage.get("output_tokens", 0) * pout) / 1e6


def _ci(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, float("nan")
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return mean, 1.96 * sd / math.sqrt(n)


def load(variant: str) -> tuple[list[dict], int]:
    d = FLOW / variant
    rows = [json.loads(line) for line in (d / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    errs = d / "errors.jsonl"
    n_err = len(errs.read_text(encoding="utf-8").splitlines()) if errs.exists() else 0
    return rows, n_err


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    variants = [v for v in ("baseline", "v1", "v2", "v3", "v4") if (FLOW / v / "results.jsonl").exists()]
    data = {v: load(v) for v in variants}

    def per_case(rows: list[dict], metric: str) -> dict[str, float]:
        acc: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            if r["status"] == "ok":
                acc[r["prompt_id"]].append(float(r["grade"][metric]))
        return {k: sum(v) / len(v) for k, v in acc.items()}

    out = ["| setup | all checks pass | Δ vs baseline (paired) | checks passed | plain text | "
           "language | $/answer | sec/answer | rows | errors |", "|---|---|---|---|---|---|---|---|---|---|"]
    base = per_case(data["baseline"][0], "pass") if "baseline" in data else {}
    for v in variants:
        rows, n_err = data[v]
        ok = [r for r in rows if r["status"] == "ok"]
        pc = per_case(rows, "pass")
        m, hw = _ci(list(pc.values()))
        delta = ""
        if v != "baseline" and base:
            common = sorted(set(pc) & set(base))
            dm, dhw = _ci([pc[c] - base[c] for c in common])
            delta = f"{dm * 100:+.0f} ± {dhw * 100:.0f} pts"
        mean = lambda k: sum(float(r["grade"][k]) for r in ok) / len(ok)  # noqa: E731
        ans_cost = sum(cost(r["model"], r["usage"]) for r in rows) / len(rows)
        lat = sum(r["latency_s"] for r in rows) / len(rows)
        trunc = sum(r["status"] == "truncated" for r in rows)
        out.append(
            f"| {LABELS.get(v, v)} | {m * 100:.0f}% ± {hw * 100:.0f} | {delta or '—'} | "
            f"{mean('checks') * 100:.0f}% | {mean('format') * 100:.0f}% | {mean('language') * 100:.0f}% | "
            f"${ans_cost:.4f} | {lat:.1f} | {len(rows)}{f' ({trunc} truncated)' if trunc else ''} | {n_err} |"
        )
    judge_total = sum(cost(r["judge_model"], r["judge_usage"]) for v in variants for r in data[v][0])
    model_total = sum(cost(r["model"], r["usage"]) for v in variants for r in data[v][0])
    n_rows = sum(len(data[v][0]) for v in variants)
    out += ["", f"Spend so far: answers ${model_total:.2f} + grading ${judge_total:.2f} "
            f"= ${model_total + judge_total:.2f} over {n_rows} graded answers "
            f"(grading ≈ ${judge_total / max(n_rows, 1):.3f} each).",
            "", "± = 95% CI half-width over per-case means; Δ is the paired per-case difference."]

    by_tag: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for v in variants:
        for r in data[v][0]:
            if r["status"] == "ok":
                by_tag[r["tags"][0]][v].append(float(r["grade"]["pass"]))
    out += ["", "| probes | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
    for tag in sorted(by_tag):
        cells = [f"{sum(by_tag[tag][v]) / len(by_tag[tag][v]) * 100:.0f}%" if by_tag[tag][v] else "—"
                 for v in variants]
        out.append(f"| {tag} | " + " | ".join(cells) + " |")

    text = "\n".join(out)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
