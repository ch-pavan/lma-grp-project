# rules vs annot_v2_glm labels, 1277 steps
Errors 0, unparsed 0. CIs: bootstrap over scenarios, 1000 draws.
Primary, mean F1 of q1:off_track: **0.1399** [0.0162, 0.3226] (only one of off_track and false_claim is expressed by the judge or present in the labels)

| question | class | precision | recall | F1 [95% CI] | support | predicted |
|---|---|---|---|---|---|---|
| q1 (n=1277) | on_track | 0.9796 | 0.777 | 0.8666 [0.8338, 0.8996] | 1233 | 978 |
| q1 (n=1277) | off_track | 0.0803 | 0.5455 | 0.1399 [0.0162, 0.3226] | 44 | 299 |
| q2 (n=1277) | none | 0.996 | 0.9937 | 0.9949 [0.991, 0.9991] | 1265 | 1262 |
| q2 (n=1277) | made_up_value | 0.4667 | 0.5833 | 0.5185 [0.125, 0.7692] | 12 | 15 |
| q2 (n=1277) | false_claim | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | 0 |
