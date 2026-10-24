# Laya without finetuning as the step judge: sweep result

Verdict: no way of using Laya typed decisions 0.4B without finetuning gives a useful step judge on BFCL. Across 4 state formats, 8 question wordings, thresholds and a logistic head on its decision probabilities, its val AUROC against the oracle labels stays between 0.39 and 0.67. Online, the two best Laya setups lose to S1 on the val pilot. Jev (hosted, classifier.dev) is the only off the shelf model with real signal, and only on closing messages. Online as block and warn it also loses to S1. So does the oracle judge, which ties S1. The correction action is the bottleneck, not judge accuracy. No variant met the bar for a full test run.

## Why Laya as is scored 0 of 133

1. Closing messages: the made up value question flagged 2,411 of 2,451 judged messages (98%), so no turn could end and every task hit the 20 step cap. As is, it flags 100% of the known good gold replay messages too.
2. Truncation: laya keeps the start of a text state (`st = state_ids[:room]` in laya/common.py, about 768 tokens of room). Our state put the proposed step and its evidence last, so on long states Laya never saw the step it was judging. The step_first format fixes this. It did not add signal.

## Setup

Labels: gold replay steps of the 89 train and val scenarios are good. Each recorded live step from an S1 run on those scenarios (356 tasks, 3,824 steps) gets the oracle verdict: a call is bad when it makes every ending of the turn's reference calls miss the reference end state. A closing message is bad when it claims success while the turn's state is wrong. 220 of 3,824 steps are bad, all in failed tasks. Thresholds and heads are fit on the 74 train scenarios and reported on the 15 val scenarios (20 bad calls and 20 bad messages there, so small). The threshold is the best train F1 with train gold false flags at or under 5%. No test scenario was used for fitting or selection.

## Offline (val split)

| Kind | Judge | Gold false flags | Live flagged | Precision | Recall | F1 | AUROC |
|---|---|---|---|---|---|---|---|
| call | Laya as is (orig state, made up value question, argmax) | 10.2% | 8.0% | | | | 0.58 |
| call | Laya dict, proceed or revise | 3.2% | 9.4% | 0.11 | 0.20 | 0.145 | 0.58 |
| call | Laya step_first, made up value | 4.5% | 8.0% | 0.07 | 0.10 | 0.080 | 0.57 |
| call | Laya logistic head, 8 features | 5.7% | 9.9% | 0.11 | 0.20 | 0.140 | 0.59 |
| call | Jev step_first, proceed or revise | 7.5% | 15.5% | 0.12 | 0.35 | 0.179 | 0.53 |
| call | Feature trees from scratch | 0.3% | 2.9% | 0.09 | 0.05 | 0.065 | 0.76 |
| msg | Laya as is (orig state, argmax) | 100% | 100% | | | | 0.58 |
| msg | Laya step_first, made up value | 6.8% | 28.9% | 0.11 | 0.40 | 0.176 | 0.59 |
| msg | Laya logistic head, 8 features | 8.5% | 9.3% | 0.09 | 0.10 | 0.093 | 0.66 |
| msg | Jev step_first, unsupported claim (yes or no) | 0.0% | 21.1% | 0.23 | 0.60 | 0.333 | 0.81 |
| msg | Jev logistic head, 3 questions | 0.0% | 22.4% | 0.25 | 0.70 | 0.373 | 0.81 |
| msg | Feature trees from scratch | 0.0% | 11.4% | 0.21 | 0.30 | 0.250 | 0.83 |

All 18 Laya pairs plus the heads are in an/table.md. Jev latency from Ada: median 662 ms, p90 900 ms per state, 3 questions per request, share_data false.

## Online pilot (15 val scenarios x 4 versions x 2 runs = 120 tasks, Qwen3 8B max length 8192)

| System | Pass | vs S1, points [95% CI] | Blocks per task | Forced quits |
|---|---|---|---|---|
| S1 no judge, run A | 25/120 (20.8%) | | 0 | 0 |
| S1 no judge, run B | 20/120 (16.7%) | -4.2 [-9.2, +0.8] | 0 | 0 |
| S_oracle (reference replay judge) | 25/120 (20.8%) | 0.0 [-6.7, +5.0] | 2.22 | 10 |
| S3 Qwen3 8B judge | 21/120 (17.5%) | -3.3 [-11.7, +5.0] | 1.98 | 2 |
| Feature trees | 17/120 (14.2%) | -6.7 [-12.5, -1.7] | 1.48 | 0 |
| Laya logistic head | 17/120 (14.2%) | -6.7 [-13.3, -0.8] | 2.33 | 11 |
| Laya step_first, made up value | 16/120 (13.3%) | -7.5 [-15.0, -1.7] | 9.65 | 57 |
| Jev on closing messages only | 15/120 (12.5%) | -8.3 [-17.5, -0.8] | 4.98 | 27 |

CIs are paired bootstrap over scenarios against S1 run A. The two S1 runs differ by 4 points, which is the noise floor of this subset. 11 to 18 tasks per system end on the 8192 token limit, in every system alike.

The oracle shows why: 44 tasks got at least one block and only 4 of them passed. 47 failures had no block at all, because the agent stopped early or skipped a call, which a judge of the proposed step cannot see. When a step is blocked, a warning and a fresh doer rarely lead to the right step.

## Code

laya_variants.py (formats, questions, LayaVariantJudge), laya_sweep.py, laya_table.py with laya_metrics.py, oracle.py with laya_labels.py, tree_judge.py with hand_clf.py, jev_client.py with jev_judge.py, laya_run.py (run.py plus the extra systems), laya_gold.py, laya_pilot_ci.py, ada/laya_body.sh. Data and outputs are in this folder.
