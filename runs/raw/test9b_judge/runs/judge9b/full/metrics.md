# llm vs test labels, 7214 steps
Errors 0, unparsed 1412. CIs: bootstrap over scenarios, 10 draws.
Primary, mean F1 of q1:off_track, q2:false_claim: **0.1154** [0.1025, 0.134]

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=7214) | on_track | 0.6759 | 0.9098 | 0.7756 [0.7676, 0.7947] | 4891 | 6584 |
| q1 (n=7214) | off_track | 0.3 | 0.0814 | 0.128 [0.1121, 0.1518] | 2323 | 630 |
| q2 (n=2043) | none | 0.8472 | 0.9523 | 0.8967 [0.8742, 0.9091] | 1718 | 1931 |
| q2 (n=2043) | made_up_value | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | 67 |
| q2 (n=2043) | false_claim | 0.4222 | 0.0585 | 0.1027 [0.077, 0.136] | 325 | 45 |
