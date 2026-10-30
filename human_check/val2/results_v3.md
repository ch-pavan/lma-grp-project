# Human check results: `human_check/val2` (annotator labels: guide v3)

100 steps, checkers pavan and shuban. Sample: half flagged by the annotators; 'reweighted' columns scale each cell back to its share of all 1668 steps.

### pavan vs shuban (checker vs checker)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 97% | 0.93 | 0.95 | 99% | 0.87 |
| calls: off track vs on track | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| calls: made up value vs none | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| turn ends: done vs not done | 50 | 94% | 0.87 | 0.89 | 95% | 0.79 |
| turn ends: four answers | 50 | 94% | 0.88 | 0.92 | 95% | 0.79 |
| turn ends: false claim vs not | 50 | 98% | 0.88 | 0.98 | 99% | 0.89 |

### Check consensus vs Swayam (Annotator A)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 93% | 0.84 | 0.87 | 98% | 0.84 |
| calls: off track vs on track | 50 | 96% | 0.90 | 0.93 | 100% | 0.93 |
| calls: made up value vs none | 50 | 100% | 1.00 | 1.00 | 100% | 1.00 |
| turn ends: done vs not done | 50 | 90% | 0.79 | 0.81 | 94% | 0.78 |
| turn ends: four answers | 50 | 90% | 0.81 | 0.86 | 94% | 0.79 |
| turn ends: false claim vs not | 50 | 92% | 0.62 | 0.90 | 95% | 0.46 |

### Check consensus vs Aaditya (Annotator B)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 86% | 0.69 | 0.75 | 97% | 0.71 |
| calls: off track vs on track | 50 | 90% | 0.76 | 0.83 | 99% | 0.82 |
| calls: made up value vs none | 50 | 98% | 0.79 | 0.98 | 100% | 0.80 |
| turn ends: done vs not done | 50 | 82% | 0.60 | 0.67 | 92% | 0.61 |
| turn ends: four answers | 50 | 80% | 0.60 | 0.73 | 91% | 0.60 |
| turn ends: false claim vs not | 50 | 88% | 0.33 | 0.85 | 96% | 0.38 |

### Swayam (Annotator A) vs Aaditya (Annotator B) on the same steps (for reference)

| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |
|---|---|---|---|---|---|---|
| all steps: problem vs fine (headline) | 100 | 91% | 0.80 | 0.84 | 97% | 0.73 |
| calls: off track vs on track | 50 | 94% | 0.85 | 0.90 | 100% | 0.89 |
| calls: made up value vs none | 50 | 98% | 0.79 | 0.98 | 100% | 0.80 |
| turn ends: done vs not done | 50 | 88% | 0.74 | 0.78 | 91% | 0.62 |
| turn ends: four answers | 50 | 86% | 0.73 | 0.81 | 90% | 0.61 |
| turn ends: false claim vs not | 50 | 92% | 0.62 | 0.90 | 95% | 0.46 |

## Decision

Headline kappa, reweighted (all steps, problem vs fine): checker vs checker 0.87; consensus vs Swayam (A) 0.84, vs Aaditya (B) 0.71; A vs B 0.73.

Lower of the two consensus-vs-annotator kappas: **0.71**, so **0.6 to 0.8: label more steps until the result is clear (proposal); passes the 0.7 bar so far**.

Per-class rows rest on 25 to 50 steps and are noisy; the headline row decides.
