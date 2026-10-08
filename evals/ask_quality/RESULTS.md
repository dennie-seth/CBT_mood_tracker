# /ask eval — results (2026-10-08)

**Decision: Claude Haiku 5.5, effort `medium`, new prompt + tool fixes** — 90% of answers
pass every check vs 12% for the previous production setup (Haiku 4.5 + old prompt),
+78 ± 18 points paired, at ~$0.001 per answer (≈9× cheaper) and 4.4 s.

20 cases × 2 reps per setup on a fictional journal; graded by Claude Opus 5.5 against
concrete per-case checks, plus programmatic plain-text and language checks.
"All checks pass" = every judge check + plain text + right language (+ required tool).

| setup | all checks pass | Δ vs baseline (paired) | checks passed | plain text | language | $/answer | sec/answer | rows | errors |
|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 + old prompt (production today) | 12% ± 14 | — | 75% | 12% | 100% | $0.0086 | 4.0 | 40 | 0 |
| Haiku 4.5 + new prompt | 55% ± 19 | +42 ± 19 pts | 82% | 82% | 100% | $0.0064 | 3.6 | 40 | 0 |
| Haiku 5.5 low + new prompt | 80% ± 17 | +68 ± 20 pts | 90% | 100% | 100% | $0.0009 | 3.6 | 40 | 0 |
| Haiku 5.5 medium + new prompt + tool fixes | 90% ± 13 | +78 ± 18 pts | 96% | 100% | 100% | $0.0010 | 4.4 | 40 | 0 |
| Haiku 5.5 low + new prompt + tool fixes | 75% ± 15 | +62 ± 19 pts | 92% | 95% | 100% | $0.0009 | 3.4 | 40 | 0 |

Spend so far: answers $0.71 + grading $3.90 = $4.62 over 200 graded answers (grading ≈ $0.020 each).

± = 95% CI half-width over per-case means; Δ is the paired per-case difference.

| probes | baseline | v1 | v2 | v3 | v4 |
|---|---|---|---|---|---|
| format | 0% | 0% | 100% | 100% | 50% |
| grounding | 0% | 100% | 100% | 100% | 100% |
| meaning | 25% | 25% | 75% | 100% | 50% |
| migraine | 0% | 0% | 0% | 0% | 0% |
| not_logged | 50% | 100% | 100% | 100% | 100% |
| russian | 0% | 17% | 67% | 67% | 50% |
| safety | 0% | 50% | 100% | 100% | 100% |
| sequence | 0% | 50% | 100% | 100% | 75% |
| tools | 100% | 100% | 100% | 100% | 100% |
| weekday | 0% | 100% | 50% | 100% | 100% |
| wording | 0% | 75% | 75% | 100% | 100% |


## Notes

- v1/v2 ran the prompt changes *before* the tool fixes (commit b24a24e); v3/v4 run the
  current code. v2 → v4 (low effort, before → after fixes) is within noise; the fixes
  target errors the eval found (weekday of an empty day, duration of an attack with no
  recorded end) rather than moving the headline.
- Known grader issue: `migraine_count` check 1 asks for the attacks' dates although the
  question doesn't, so it fails every setup equally (the "migraine" row). Left as-is so
  scores aren't re-tuned after seeing results; reword it before the next run.
- Today's production answers mostly failed on Markdown (asterisks in Telegram), formal
  «вы» in Russian, causal claims from sequence, and the safety case.
- Noise floor for a 20-case × 2-rep pass rate is roughly ±15 points: big gaps are real,
  low vs medium effort is not cleanly separated.
