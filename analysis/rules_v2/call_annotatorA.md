# rules vs annot_v2_deepseek labels, 1277 steps
Errors 0, unparsed 0. CIs: bootstrap over scenarios, 1000 draws.
Primary, mean F1 of q1:off_track: **0.1628** [0.031, 0.3514] (only one of off_track and false_claim is expressed by the judge or present in the labels)

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=1277) | on_track | 0.9826 | 0.78 | 0.8697 [0.838, 0.9028] | 1232 | 978 |
| q1 (n=1277) | off_track | 0.0936 | 0.6222 | 0.1628 [0.031, 0.3514] | 45 | 299 |
| q2 (n=1277) | none | 0.9952 | 0.9929 | 0.9941 [0.9882, 0.9994] | 1265 | 1262 |
| q2 (n=1277) | made_up_value | 0.4 | 0.5 | 0.4444 [0.2, 0.6667] | 12 | 15 |
| q2 (n=1277) | false_claim | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | 0 |
