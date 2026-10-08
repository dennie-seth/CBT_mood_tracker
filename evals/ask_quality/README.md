# /ask eval

Measures the `/ask` assistant (AiService + tools) on a **fictional** 3-week journal —
never real user data. 20 cases (see `cases.md`), each with concrete checks graded by
Claude Opus 5.5, plus programmatic plain-text / language checks. Latest numbers:
`RESULTS.md`.

```bash
# one setup (writes .claude/hillclimb/ask_quality/<variant>/)
python evals/ask_quality/run_eval.py --variant v5 --model claude-haiku-5-5 --effort medium --reps 2
# compare an older app version: point --app-root at a checkout of it
python evals/ask_quality/run_eval.py --variant baseline --model ... --app-root ../checkout
# grader sanity check (known-good must pass, empty / "I don't know" / wrong answer must fail)
python evals/ask_quality/selftest_grader.py
# summary table + cost
python evals/ask_quality/summarize.py
```

Reads `ANTHROPIC_API_KEY` from `.env`. Cost: ~$0.02 per graded answer (mostly the
grader), so ~$1 per setup. After any change to the harness files the runner exits
until the repo owner re-runs it with `--approve-harness`. Infra failures go to
`errors.jsonl` (re-run automatically on resume), never into the scores.
