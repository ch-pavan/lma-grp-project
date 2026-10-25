# llm vs val labels, 1772 steps
Errors 0, unparsed 328. CIs: bootstrap over scenarios, 1000 draws.
Primary, mean F1 of q1:off_track, q2:false_claim: **0.1541** [0.091, 0.2066]

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=1772) | on_track | 0.933 | 0.9211 | 0.927 [0.8933, 0.953] | 1648 | 1627 |
| q1 (n=1772) | off_track | 0.1034 | 0.121 | 0.1115 [0.0694, 0.1595] | 124 | 145 |
| q2 (n=495) | none | 0.9095 | 0.9708 | 0.9391 [0.9139, 0.9622] | 445 | 475 |
| q2 (n=495) | made_up_value | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | 9 |
| q2 (n=495) | false_claim | 0.5455 | 0.12 | 0.1967 [0.0769, 0.3137] | 50 | 11 |
