# Step head without "breaks task", and the done-check threshold by cross-validation (plan items 3.7 and 3.4, 31 Oct 2026)

Both items ran on Ada (RTX 2080 Ti, fp16 with a GradScaler, gradient accumulation 8) with the job scripts in `runs/ada/` (see `runs/ada/README.md`). The data variants come from `analysis/make_step_variant.py` and `analysis/make_done_folds.py`. The raw outputs are in `runs/data/laya_runs/{ada_step_nobt,ada_done_cv}/`, and the scored tables are in `analysis/gpu_2026-10-31/`.

## 3.7: step head trained without the oracle "breaks task" label

**Why.** The step head was trained on an oracle off-track rule whose largest part, "breaks task" (276 of 408 bad training calls), failed the 80% agreement rule. This item retrains the head without that part (`nobt`: 209 bad training calls, 97 bad validation calls) and, as a control, retrains the original labels (`orig`) under the same Ada settings. Each variant has 3 seeds, and each run picks its threshold on the dev scenarios.

| variant (3 seeds, mean ± sd) | AUROC, oracle with bt | AUROC, oracle without bt | off-track F1 vs Annotator A | vs Annotator B | vs both agree |
|---|---|---|---|---|---|
| without "breaks task" (`nobt`) | 0.78 ± 0.03 | 0.97 ± 0.01 | 0.41 ± 0.06 | 0.35 ± 0.07 | 0.37 ± 0.08 |
| original labels (`orig`) | 0.87 ± 0.01 | 0.94 ± 0.02 | 0.41 ± 0.16 | 0.35 ± 0.15 | 0.39 ± 0.19 |
| reference: job 49656 (bf16, one seed, in the mid report) | 0.90 | | 0.42 | 0.36 | 0.39 |

The off-track F1 columns score the head on the 1,277 tool calls of the 9B validation run against the guide v2 annotator labels (45 and 44 positives), as in `analysis/primary_val.py`.

**Reading:**
- **Dropping "breaks task" does not change agreement with the annotators.** Off-track F1 is 0.41 / 0.35 / 0.37 without it and 0.41 / 0.35 / 0.39 with it. The difference is far smaller than the seed spread.
- **Each head is best at its own training target.** The `nobt` head ranks the reduced oracle label better (AUROC 0.97 against 0.94) and the full label worse (0.78 against 0.87). This is expected and says nothing about which label is right.
- **Seed variation is large.** With the original labels, off-track F1 ranges from 0.17 to 0.53 across seeds and label sets, while the oracle AUROC stays between 0.86 and 0.88. The F1 depends on a dev threshold chosen on few dev positives (0.03 to 0.18 for these seeds). The `nobt` seeds are steadier (0.28 to 0.46). The single-seed numbers in the mid report (job 49656) sit inside the `orig` range, but any Laya against 9B gap of a few F1 points is within seed noise.
- **Ada against the original run.** The `orig` seeds reproduce the job 49656 setup in fp16 on 2080 Ti cards. Their AUROC on the full oracle label is 0.86 to 0.88, slightly below the 0.90 of job 49656 (bf16).
- **The mid report's offline step table (1,277 calls of the 9B run, 109 bad).** Job 49656 gives AUROC 0.91 and F1 0.59 there. The `orig` seeds give 0.87 ± 0.01 and 0.47 ± 0.07, and `nobt` gives 0.79 ± 0.03 and 0.47 ± 0.05. The report's numbers are therefore the best run, not the typical one. Every run still ranks bad calls far better than the 9B SLM judge (AUROC 0.61, F1 0.24).
- **Against the 9B judge on the annotator labels.** The 9B judge scores off-track F1 0.34 / 0.29 / 0.29 on tool calls (`analysis/primary_val.py`). The `orig` seed mean, 0.41 / 0.35 / 0.39, is close to the single-seed result. One of the three seeds (0.22 / 0.18 / 0.17) falls below the judge, though, so the tool-call lead is not yet reliable.

**Decision for the final.** Keep the original labels for now, because removing "breaks task" neither helps nor hurts agreement with the annotators. Report step-head results as mean ± sd over 3 seeds, not one seed. A steadier threshold rule, such as choosing it on out-of-fold scores as in 3.4, is worth testing.

## 3.4: done-check threshold chosen by grouped cross-validation on train

**Why.** The done head was reported at 0.5 and at a dev threshold of 0.9835 picked on 8 dev scenarios, which gave very different F1 (0.53 against 0.36). This item picks the threshold on train only: 5 folds grouped by scenario, 2 epochs each, scoring the held-out fold. The F1-maximising threshold on the pooled out-of-fold scores is then fixed before looking at validation.

| fold | held-out turn ends | not done | best threshold on the fold | F1 there |
|---|---|---|---|---|
| 0 | 679 | 112 | 0.17 | 0.52 |
| 1 | 690 | 145 | 0.32 | 0.62 |
| 2 | 700 | 138 | 0.47 | 0.56 |
| 3 | 630 | 109 | 0.41 | 0.52 |
| 4 | 642 | 118 | 0.87 | 0.59 |

Pooled out of fold (3,341 turn ends, 622 not done): best threshold **0.561**, F1 0.54.

| threshold on validation (495 turn ends, job 49265 scores) | how chosen | precision | recall | F1 |
|---|---|---|---|---|
| 0.561 | out of fold on train (this item) | 0.55 | 0.51 | **0.53** |
| 0.5 | default, as in the live runs | 0.54 | 0.52 | 0.53 |
| 0.9835 | dev split of 8 scenarios (job 49265) | 0.93 | 0.23 | 0.36 |

**Reading:**
- **The train-only threshold agrees with 0.5.** It gives validation F1 0.53, the same as 0.5. The dev threshold of 0.9835 was an artefact of the small dev split.
- **Per-fold thresholds are unstable** (0.17 to 0.87), so a threshold from one small split should not be trusted. Pooling the folds fixes this.
- **Decision for the final.** Report the done check at 0.561, the threshold fixed on train before validation, with 0.5 alongside. Drop the dev-split threshold.

## Reproduce

From the repo root, after `sh runs/unpack_data.sh`:

```
python analysis/score_step_variants.py runs/data/laya_runs/ada_step_nobt --out analysis/gpu_2026-10-31/step_nobt.md
python analysis/done_threshold_cv.py runs/data/laya_runs/ada_done_cv --out analysis/gpu_2026-10-31/done_cv.md
```
