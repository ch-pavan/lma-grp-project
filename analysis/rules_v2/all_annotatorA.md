# rules vs annot_v2_deepseek labels, 1772 steps
Errors 0, unparsed 0. CIs: bootstrap over scenarios, 1000 draws.
Primary, mean F1 of q1:off_track, q2:false_claim: **0.0683** [0.0124, 0.1507]

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=1772) | on_track | 0.9437 | 0.8368 | 0.887 [0.857, 0.9158] | 1661 | 1473 |
| q1 (n=1772) | off_track | 0.0936 | 0.2523 | 0.1366 [0.0248, 0.3014] | 111 | 299 |
| q2 (n=1772) | none | 0.988 | 0.9903 | 0.9891 [0.9859, 0.9926] | 1745 | 1749 |
| q2 (n=1772) | made_up_value | 0.4 | 0.5 | 0.4444 [0.2, 0.6667] | 12 | 15 |
| q2 (n=1772) | false_claim | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 15 | 8 |
