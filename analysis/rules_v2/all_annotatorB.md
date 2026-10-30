# rules vs annot_v2_glm labels, 1772 steps
Errors 0, unparsed 0. CIs: bootstrap over scenarios, 1000 draws.
Primary, mean F1 of q1:off_track, q2:false_claim: **0.0609** [0.007, 0.1429]

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=1768) | on_track | 0.9517 | 0.8356 | 0.8899 [0.8618, 0.9169] | 1673 | 1469 |
| q1 (n=1768) | off_track | 0.0803 | 0.2526 | 0.1218 [0.0139, 0.2857] | 95 | 299 |
| q2 (n=1768) | none | 0.9914 | 0.9908 | 0.9911 [0.9877, 0.9944] | 1746 | 1745 |
| q2 (n=1768) | made_up_value | 0.4667 | 0.5833 | 0.5185 [0.125, 0.7692] | 12 | 15 |
| q2 (n=1768) | false_claim | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 10 | 8 |
