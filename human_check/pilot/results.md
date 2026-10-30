# Human check results: `human_check/pilot` (annotator labels: guide v2)

100 steps, checkers aaditya and swayam. Sample: half flagged by the LLM annotators; 'reweighted' columns scale each cell back to its share of all 1768 steps.

### aaditya vs swayam (checker vs checker)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 94% | 0.88 | 0.88 | 97% | 0.89 |
| calls: off track vs on track | 50 | 96% | 0.90 | 0.93 | 100% | 0.93 |
| calls: made up value vs none | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| turn ends: done vs not done | 50 | 92% | 0.84 | 0.84 | 92% | 0.80 |
| turn ends: four answers | 50 | 92% | 0.86 | 0.90 | 92% | 0.81 |
| turn ends: false claim vs not | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |

### Check consensus vs Annotator A (DeepSeek V4.1 Flash)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 71% | 0.39 | 0.45 | 90% | 0.42 |
| calls: off track vs on track | 50 | 80% | 0.52 | 0.66 | 98% | 0.66 |
| calls: made up value vs none | 50 | 94% | 0.54 | 0.93 | 96% | 0.16 |
| turn ends: done vs not done | 50 | 68% | 0.33 | 0.38 | 80% | 0.37 |
| turn ends: four answers | 50 | 66% | 0.36 | 0.59 | 80% | 0.38 |
| turn ends: false claim vs not | 50 | 94% | 0.37 | 0.93 | 98% | 0.39 |

### Check consensus vs Annotator B (GLM-5.3-Flash)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 89% | 0.77 | 0.79 | 93% | 0.60 |
| calls: off track vs on track | 50 | 96% | 0.90 | 0.93 | 100% | 0.93 |
| calls: made up value vs none | 50 | 96% | 0.65 | 0.95 | 96% | 0.17 |
| turn ends: done vs not done | 50 | 86% | 0.71 | 0.73 | 87% | 0.59 |
| turn ends: four answers | 50 | 84% | 0.69 | 0.81 | 86% | 0.58 |
| turn ends: false claim vs not | 50 | 98% | 0.79 | 0.98 | 99% | 0.80 |

### Annotator A (DeepSeek V4.1 Flash) vs Annotator B (GLM-5.3-Flash) on the same steps (for reference)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 76% | 0.49 | 0.55 | 95% | 0.66 |
| calls: off track vs on track | 50 | 84% | 0.63 | 0.72 | 98% | 0.74 |
| calls: made up value vs none | 50 | 94% | 0.54 | 0.93 | 99% | 0.57 |
| turn ends: done vs not done | 50 | 74% | 0.44 | 0.51 | 90% | 0.59 |
| turn ends: four answers | 50 | 72% | 0.45 | 0.66 | 89% | 0.57 |
| turn ends: false claim vs not | 50 | 92% | 0.29 | 0.91 | 97% | 0.32 |

## Decision

Headline kappa, reweighted (all steps, problem vs fine): checker vs checker 0.89; consensus vs Annotator A 0.42, vs Annotator B 0.60; A vs B 0.66.

Lower of the two consensus-vs-annotator kappas: **0.42**, so **below 0.6: rewrite the guide and relabel (proposal)**.

Per-class rows rest on 25 to 50 steps and are noisy; the headline row decides.
