# Human check results: `human_check/val2` (annotator labels: guide v2)

100 steps, checkers aaditya and swayam. Sample: half flagged by the LLM annotators; 'reweighted' columns scale each cell back to its share of all 1668 steps.

### aaditya vs swayam (checker vs checker)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 97% | 0.93 | 0.95 | 99% | 0.87 |
| calls: off track vs on track | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| calls: made up value vs none | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| turn ends: done vs not done | 50 | 94% | 0.87 | 0.89 | 95% | 0.79 |
| turn ends: four answers | 50 | 94% | 0.88 | 0.92 | 95% | 0.79 |
| turn ends: false claim vs not | 50 | 98% | 0.88 | 0.98 | 99% | 0.89 |

### Check consensus vs Annotator A (DeepSeek V4.1 Flash)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 83% | 0.65 | 0.68 | 97% | 0.71 |
| calls: off track vs on track | 50 | 90% | 0.78 | 0.82 | 99% | 0.84 |
| calls: made up value vs none | 50 | 92% | 0.30 | 0.91 | 99% | 0.33 |
| turn ends: done vs not done | 50 | 82% | 0.63 | 0.65 | 92% | 0.66 |
| turn ends: four answers | 50 | 80% | 0.65 | 0.75 | 91% | 0.64 |
| turn ends: false claim vs not | 50 | 94% | 0.74 | 0.92 | 98% | 0.76 |

### Check consensus vs Annotator B (GLM-5.3-Flash)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 83% | 0.61 | 0.70 | 97% | 0.66 |
| calls: off track vs on track | 50 | 90% | 0.76 | 0.83 | 99% | 0.82 |
| calls: made up value vs none | 50 | 96% | 0.65 | 0.95 | 100% | 0.67 |
| turn ends: done vs not done | 50 | 80% | 0.54 | 0.65 | 91% | 0.56 |
| turn ends: four answers | 50 | 80% | 0.58 | 0.76 | 91% | 0.57 |
| turn ends: false claim vs not | 50 | 92% | 0.46 | 0.91 | 97% | 0.49 |

### Annotator A (DeepSeek V4.1 Flash) vs Annotator B (GLM-5.3-Flash) on the same steps (for reference)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 76% | 0.50 | 0.55 | 97% | 0.66 |
| calls: off track vs on track | 50 | 88% | 0.73 | 0.78 | 99% | 0.82 |
| calls: made up value vs none | 50 | 88% | 0.18 | 0.86 | 99% | 0.25 |
| turn ends: done vs not done | 50 | 74% | 0.46 | 0.51 | 92% | 0.61 |
| turn ends: four answers | 50 | 74% | 0.52 | 0.68 | 92% | 0.62 |
| turn ends: false claim vs not | 50 | 90% | 0.50 | 0.88 | 97% | 0.53 |

## Decision

Headline kappa, reweighted (all steps, problem vs fine): checker vs checker 0.87; consensus vs Annotator A 0.71, vs Annotator B 0.66; A vs B 0.66.

Lower of the two consensus-vs-annotator kappas: **0.66**, so **0.6 to 0.8: label more steps until the result is clear (proposal); under the 0.7 bar so far**.

Per-class rows rest on 25 to 50 steps and are noisy; the headline row decides.
