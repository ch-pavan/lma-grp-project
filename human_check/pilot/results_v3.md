# Human check results: `human_check/pilot` (annotator labels: guide v3)

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
| all steps: problem vs fine (headline) | 100 | 91% | 0.81 | 0.83 | 98% | 0.88 |
| calls: off track vs on track | 50 | 96% | 0.90 | 0.93 | 100% | 0.93 |
| calls: made up value vs none | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| turn ends: done vs not done | 50 | 86% | 0.71 | 0.73 | 92% | 0.78 |
| turn ends: four answers | 50 | 86% | 0.74 | 0.83 | 92% | 0.79 |
| turn ends: false claim vs not | 50 | 96% | 0.48 | 0.96 | 98% | 0.49 |

### Check consensus vs Annotator B (GLM-5.3-Flash)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 86% | 0.70 | 0.74 | 93% | 0.71 |
| calls: off track vs on track | 50 | 90% | 0.76 | 0.83 | 95% | 0.51 |
| calls: made up value vs none | 50 | 96% | 0.65 | 0.95 | 100% | 0.95 |
| turn ends: done vs not done | 50 | 86% | 0.71 | 0.73 | 90% | 0.70 |
| turn ends: four answers | 50 | 84% | 0.69 | 0.81 | 89% | 0.70 |
| turn ends: false claim vs not | 50 | 96% | -0.00 | 0.96 | 98% | 0.00 |

### Annotator A (DeepSeek V4.1 Flash) vs Annotator B (GLM-5.3-Flash) on the same steps (for reference)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 89% | 0.77 | 0.79 | 95% | 0.76 |
| calls: off track vs on track | 50 | 94% | 0.86 | 0.90 | 96% | 0.58 |
| calls: made up value vs none | 50 | 96% | 0.65 | 0.95 | 100% | 0.95 |
| turn ends: done vs not done | 50 | 88% | 0.75 | 0.77 | 93% | 0.79 |
| turn ends: four answers | 50 | 86% | 0.73 | 0.83 | 92% | 0.78 |
| turn ends: false claim vs not | 50 | 96% | -0.00 | 0.96 | 98% | 0.00 |

## Decision

Headline kappa, reweighted (all steps, problem vs fine): checker vs checker 0.89; consensus vs Annotator A 0.88, vs Annotator B 0.71; A vs B 0.76.

Lower of the two consensus-vs-annotator kappas: **0.71**, so **0.6 to 0.8: label more steps until the result is clear (proposal); passes the 0.7 bar so far**.

Per-class rows rest on 25 to 50 steps and are noisy; the headline row decides.
