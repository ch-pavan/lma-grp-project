# Qwen3.5 9B as the agent, no judge: results and failure analysis (24 Oct 2026)

First runs of our own agent model. Same harness, split and oracle as Shuban's runs (`shuban_findings/`), so the numbers sit next to his Qwen3 8B and Qwen3.5 4B results.

## Setup

| Item | Value |
|---|---|
| Agent (planner and doer) | `cyankiwi/Qwen3.5-9B-AWQ-4bit`, commit `e4d2d39`, text only (`--language-model-only`) |
| Judge | none: system `S1_record` (S1 behaviour, every step's judge input saved for labelling) |
| Harness | Shuban's `actions.py` / `run.py` (planner, doer, 20 step cap per turn, empty turn check) |
| Benchmark | BFCL v4 multi turn, gorilla commit `6ea5797`, split from `finetune_data/split.json` (74 train, 15 val, 100 test, 11 dropped) |
| Serving | vLLM 0.27.1 (Shuban: 0.19.1), one RTX 6000 Ada 48 GB on Turing node01, `--max-model-len 32768` (Shuban: 16k to 20k), `--max-num-seqs 128`, prefix caching, `qwen3_coder` tool parser |
| Sampling | as in Shuban's runs: temperature 0.7, top p 0.8, top k 20 with reasoning off; 0.6 / 0.95 with reasoning on |
| Reasoning on | `AGENT_THINK=1`: every planner and doer call thinks, no output cap (only the 32k context) |
| Runs | val 15 scenarios x 4 versions x 2 runs = 120 tasks, with reasoning off and on; train 74 x 4 x 3 = 888 tasks, reasoning off |
| Cost | job 49146, 1 GPU, 67 minutes for all 1,128 tasks plus 6 canary tasks |

The harness was checked first: gold replay passes 755 of 756 tasks (`multi_turn_miss_func_49` fails BFCL's response check; it is a test scenario). Job scripts: `runs/turing/q9b_s1t.sbatch`. Raw outputs on Turing: `~/stay-on-task/runs/q9b_s1t_49146/`.

## Pass rates

Same 120 val tasks for every row. 95% CIs are a bootstrap over the 15 val scenarios, so they are wide.

| Agent | Pass % [95% CI] | base | miss_param | miss_func | long_context | s per task |
|---|---|---|---|---|---|---|
| Qwen3 8B AWQ (Shuban) | 25.8 [9.2, 44.2] | | | | | 162 |
| Qwen3.5 4B AWQ (Shuban) | 40.0 [24.2, 55.8] | | | | | 101 |
| **Qwen3.5 9B AWQ, reasoning off** | **43.3 [27.5, 60.0]** | 60.0 | 40.0 | 23.3 | 50.0 | 376 |
| Qwen3.5 9B AWQ, reasoning on | 36.7 [20.0, 53.3] | 40.0 | 43.3 | 25.0 | 40.0 | 931 |

Train (888 tasks, reasoning off): 52.7% [44.8, 60.5]; base 61.3, miss_param 56.8, miss_func 37.8, long_context 55.0.

- The 9B is a little better than the 4B, inside the noise. The Qwen3.5 generation matters more than size (8B Qwen3 is far below both).
- Reasoning on does not help: 6.6 points lower, 2.5x slower per task, and it gives up more often (below).
- Seconds per task are not comparable with Shuban's: our server ran up to 128 tasks at once on one card.

## Why tasks fail

Each failed task is assigned the type of its first unfinished turn (`analysis/oracle_labels.py`).

| Failure type | What it means | val, off | val, on | train, off |
|---|---|---|---|---|
| omission_stopped | ended the turn early, no success claim (often after a fixable error) | 26.5% | 46.1% | 19.0% |
| omission_claimed_done | said it was done, the state says not | 17.6% | 6.6% | 12.1% |
| omission_asked_user | asked the user although the request was answerable | 8.8% | 10.5% | 26.2% |
| wrong_step | a call that made the right end state unreachable | 23.5% | 17.1% | 23.8% |
| acted_instead_of_asking | changed state on a turn where the right move was to ask (missing parameter or function) | 22.1% | 11.8% | 13.3% |
| checker_only, step_cap | every turn looks done to the oracle but BFCL's checker fails it; or hit the 20 step cap | 1.5% | 7.9% | 5.4% |
| **failed tasks** | | 68 | 76 | 420 |

Roughly half of failures are **unfinished turns** (stopped, claimed done, asked needlessly) and half are **bad steps** (wrong step, acted instead of asking). This matches Shuban's finding for Qwen3 8B: a judge of the proposed step cannot see an omission, which is why block and warn did not help even with the oracle.

## Labels for training

Automatic labels from replay, no hand labelling yet.

| Label | Unit | val, off | train, off |
|---|---|---|---|
| off track (strict rule, endings = suffixes of the reference calls) | tool call | 63 of 1,277 (4.9%) | 230 of 8,806 (2.6%) |
| off track (proposal rule, endings = ordered subsets) | tool call | 63 of 1,277 (4.9%) | 221 of 8,806 (2.5%) |
| false claim (success words while the state is wrong) | closing message | 50 of 495 (10.1%) | 281 of 3,737 (7.5%) |
| **turn not done** (end state differs, or a reference function was never called) | turn end | 111 of 495 (22.4%) | 672 of 3,737 (18.0%) |

- `oracle_labels.py` reproduces Shuban's `laya_labels.py` exactly on the strict rule (0 differences on 870 steps).
- The proposal's more forgiving rule (any ordered subset of the reference calls as the ending) changes 9 of about 10,000 call labels. Detours are not distorting the step labels on BFCL.
- The turn end label is far better balanced than the step labels (18 to 22% against 2.5 to 5%): train alone gives 672 unfinished turns, above the proposal's Gate 1 of 300 per class.

## Domains and risky actions

BFCL multi turn mixes eight simulated apps; most tasks use two or three.

| App | Tasks (val + train) | Failed |
|---|---|---|
| VehicleControlAPI | 292 | 53.4% |
| GorillaFileSystem | 284 | 59.2% |
| MessageAPI | 232 | 54.7% |
| TradingBot | 220 | 15.9% |
| TravelAPI | 212 | 60.8% |
| TwitterAPI | 176 | 62.5% |
| MathAPI | 148 | 45.3% |
| TicketAPI | 120 | 55.8% |

The 9B ran 1,860 calls from the irreversible list (rm, send_message, post_tweet, place_order, withdraw_funds, book_flight and so on); 156 of them (8%) were off track by the oracle. MathAPI calls change no state, so for math only the turn end question (was the calculation done and passed on) applies.

## Worked example: `multi_turn_base_93`, val, run 0 (failed)

Vehicle control. Turn 0, "How much fuel do I have?": one correct call, done.

Turn 1, "Fill it to full, start the engine with START, check the tire pressure". Reference: `fillFuelTank(39.5)`, `lockDoors(...)`, `pressBrakePedal(1.0)`, `startEngine('START')`, `check_tire_pressure()`. The 9B called `fillFuelTank(50)` (error: above tank capacity), `startEngine('START')` (error: all doors must be locked first, naming the unlocked doors) and `check_tire_pressure()`, then reported what it could not do and ended the turn. Not done; missing `lockDoors`, `pressBrakePedal`.

Turn 2, "If tire pressure is below 40 psi, give me directions to the nearest tire shop". Reference: `find_nearest_tire_shop()`, `set_navigation('456 Oakwood Avenue...')`. The 9B found the shop and told the user the address, but never set the navigation. Not done; missing `set_navigation`.

No call here was harmful. Turn 1 is an easy catch (the agent says it could not finish); turn 2 is a subtle one (the agent is confident, and "directions" has to be read as setting the navigation). Subtle cases like turn 2 are where the 9B SLM judge with reasoning may beat a 0.4B classifier.

## What it means for the project

1. **Two checks, two jobs.** Before a step: should this run (off track, made up value, unneeded irreversible call)? That is about harm and catches the bad step half of failures. At turn end: is the request really done (unfinished, false claim, should have asked)? That is about finishing and catches the other half, and it is the only correction that moved task accuracy in Shuban's runs (oracle with rollback and done check +5.8 on Qwen3 8B, +9.2 on Qwen3.5 4B).
2. **Main finetuning target: a typed turn end question** (`done`, `missing_action`, `should_ask_user`, `unsupported_claim`) next to the per step questions. The turn end labels are balanced and come straight from the reference end state.
3. **Agent with reasoning off.** Reasoning on is slower and no better.
4. **The 9B SLM judge stays as the baseline**, and as the escalation target only if it beats Laya on the cases Laya is unsure about. If it does not, unsure cases go to "ask the user" instead.

## Caveats

- One val run pair on 15 scenarios: differences under about 10 points are inside the noise. Shuban measured 4.2 points between two identical no judge runs.
- vLLM 0.27.1 and a 32k context against Shuban's 0.19.1 and 16k to 20k: fewer of our tasks can fail on context length, so our pass rates may be slightly higher for that reason alone.
- Labels come from the BFCL replay oracle. They follow BFCL's own definition of a pass but have not been checked by people or by the two LLM annotators yet. Known limits: read only calls are never flagged; the false claim label needs a success word; only the first fatal call of a turn is flagged.

## Next

1. Hand check about 100 oracle labels (two of us), and run the LLM annotator check on a sample (proposal's 80% rule).
2. Build the Laya training set: typed turn end labels and step labels from these 1,008 tasks plus Shuban's Qwen3 8B steps, split by scenario.
3. Finetune Laya (head only, then full; tail first state packing; temperature calibration) and one or two other small decision models; compare offline with Laya as is, the 9B SLM judge (4,096+ reasoning tokens), Jev and plain rules.
4. Online on the 120 val tasks: no judge, SLM judge, finetuned Laya and the oracle, each with rollback and the turn end check.
5. Revise the proposal to the two check design.

## Update, same day: annotators, Laya finetune, live done check

### LLM annotators on val (OpenCode Go, about $1.20 for 3,544 calls)

DeepSeek V4.1 Flash and GLM-5.3-Flash labelled all 495 val turn ends (typed: done, missing_action, should_ask_user, unsupported_claim) and all 1,277 val calls (Q1, Q2 with the judge guide). Scripts: `analysis/annotate.py`, `analysis/agreement.py`.

| Comparison | Turn ends: agree / kappa / AC1 | Calls (off track): agree / kappa |
|---|---|---|
| DeepSeek vs GLM | 85% / 0.54 / 0.77 | 93% / 0.61 |
| DeepSeek vs oracle | 76% / 0.35 / 0.63 | 85% / 0.08 |
| GLM vs oracle | 82% / 0.41 / 0.74 | 89% / 0.04 |

- The turn end label holds up moderately: where both LLMs agree, they match the oracle 85% of the time. Disagreements go both ways (the oracle requires every reference read call; the LLMs miss state errors hidden by a confident message).
- The oracle's per call "off track" label does not match what the LLMs call off track (kappa near 0). It fails the proposal's 80% rule and must be rewritten before training.
- Concurrency on OpenCode Go: GLM-5.3-Flash ran clean at 64 parallel calls; DeepSeek V4.1 Flash returned many 429s at 96 (retried, nothing lost) and none at 48.

### Narrower step labels (`analysis/step_labels.py`)

| Label (from the reference calls and the code made evidence list) | val calls | train calls | LLMs flag it |
|---|---|---|---|
| unneeded irreversible (irreversible function not in the turn's reference) | 57 | 167 | 58 to 68% |
| wrong irreversible (right function, different arguments) | 73 | 179 | 18 to 33% |
| made up value (source "nowhere", not a reference value) | 15 | 74 | 33 to 47% |
| breaks task (current oracle rule) | 63 | 221 | 14 to 25% |

Unneeded irreversible is the clearest step label. All four are below the 300 positives of Gate 1 in train, so directed runs are needed for the step heads.

### Laya finetune on the turn end done check (`analysis/train_laya_done.py`)

Laya typed decisions 0.4B (`convaiinnovations/laya-typed-decisions` at `e929ae5`, laya 0.3.27), one choice question (done, not_done), oracle labels. Train 3,341 turn ends (66 train scenarios), dev 396 (8 held out train scenarios, epoch and threshold choice), val 495 (only reported). One RTX 6000 Ada; head only 6 epochs in 2.5 min (job 49262); full finetune 4 epochs in 5 min with gradient checkpointing and micro batches of 8 (job 49265; the first try without them ran out of memory). Full finetune is best after epoch 2 and overfits after.

Offline, val turn ends, positive class not done, against the oracle:

| Checker | AUROC | F1 not done |
|---|---|---|
| Laya as is | 0.53 | 0.20 |
| Laya head only | 0.59 | 0.34 |
| **Laya full finetune** (threshold 0.5) | **0.79** | **0.53** |
| Qwen3.5 9B SLM judge, reasoning on, same prompt as the annotators | | 0.41 |
| DeepSeek V4.1 Flash | | 0.50 |
| GLM-5.3-Flash | | 0.52 |

The dev chosen threshold (0.984, from 50 dev positives) gave val F1 0.36; the 0.53 row uses the default 0.5, not tuned on val (the best threshold on val, chosen by peeking, gives 0.55). Next time the threshold should come from grouped cross validation on train.

### Live done check on the 120 val tasks (job 49274, `runs/turing/q9b_dc.sbatch`)

Same server as before (vLLM 0.27.1, 32k, reasoning off for the agent). Mode `dc`: when the agent closes a turn the checker answers done or not; not done drops the closing message and adds "Part of the request may be unfinished. Check it, and continue if something is left." (at most 2 per turn). Laya's threshold 0.5 was fixed before the run. CIs are a paired bootstrap over the 15 scenarios.

| System | Pass | vs no judge [95% CI] | Not done per task | Judge tokens per task | s per task |
|---|---|---|---|---|---|
| no judge (rerun; first run was also 43.3) | 43.3% | | 0 | 0 | 207 |
| **finetuned Laya done check** | **45.8%** | **+2.5 [-5.0, +10.8]** | 1.53 | about 0 (0.4B classifier) | 234 |
| 9B SLM judge done check, reasoning on | 43.3% | +0.0 [-5.8, +7.5] | 0.85 | 10,334 | 454 |
| oracle done check (ceiling) | 46.7% | +3.3 [-5.0, +12.5] | 1.95 | 0 | 235 |

- Laya beats the 9B SLM judge offline (F1 0.53 vs 0.41) and online (+2.5 vs +0.0) at almost no judge cost and half the time per task, and gets close to the oracle ceiling.
- No online difference is significant: 120 tasks is too few, and with this agent the ceiling of the done check alone is small (+3.3). Shuban's oracle with rollback and the done check reached +9.2 on Qwen3.5 4B, so a step checker that drives rollback is the lever with the larger ceiling.
- The 9B judge thinks about 2,400 tokens per done check (93 s each under load); 20 of 495 offline answers did not parse.

### Annotator guide v2 on val (`annotate.py --guide v2`, about $1.20)

Rewrite aimed at the v1 disagreements (DeepSeek said unsupported_claim where GLM said done in 36 turn ends; DeepSeek called retries, navigation and reads off track in 65 calls). Turn ends: checks in a fixed order, extra detail from earlier turns or values that could sit in a cut output are not unsupported claims, should_ask_user only for state changes, asking for a value a tool could look up is missing_action. Calls: off track only for one of five named reasons (wrong target, unrequested change, goal swap, early stop, should ask), reads, navigation, logins and retries are on track, on track when unsure. Same models, same 495 turn ends and 1,277 calls, blind to the oracle.

| Comparison | v1: agree / kappa / AC1 | v2: agree / kappa / AC1 |
|---|---|---|
| Turn ends, DeepSeek vs GLM (done vs not) | 85% / 0.54 / 0.77 | 90% / 0.61 / 0.87 |
| Turn ends, four typed answers | 84% / 0.54 / 0.82 | 90% / 0.62 / 0.89 |
| Calls off track, DeepSeek vs GLM | 93% / 0.61 / 0.92 | **98% / 0.73 / 0.98** |
| Turn ends, both agree, vs oracle | 85% / 0.47 / 0.78 | 86% / 0.44 / 0.81 |
| Calls off track vs oracle (DeepSeek, GLM) | kappa 0.08, 0.04 | kappa 0.15, 0.11 |

- Calls now clear the 0.7 bar. Flags dropped from 175 and 115 to 45 and 44, and are more precise: 39 and 37 of the 54 calls each flags (off track or made up value) carry one of the four step labels, against 74 of 175 and 51 of 115 under v1.
- Turn ends improve but stay under 0.7 (0.61). The rest of the split is mostly missing_action vs done when the agent asks the user or stops after an error; the 100 step human pilot decides these.
- The oracle's off track label still disagrees with both LLMs under v2 (kappa 0.11 to 0.15), so it stays out of training; the narrower step labels replace it.
- v1 stays the default in `annotate.py` so the earlier numbers reproduce.

### Deferred: human adjudication round for turn ends (planned, not run yet)

The call labels pass (kappa 0.73) and are used from now on. The turn end labels (kappa 0.61) wait for one human round, done later so it does not block the finetune work:

1. Two of us label about 100 val turn ends blind to the LLM answers and the oracle: the 52 where DeepSeek and GLM split under v2 (listed in `analysis/v2_turn_disagreements.jsonl`: 31 missing_action vs done, 12 unsupported_claim vs done, 4 should_ask_user vs done, 5 other or unparsed) plus about 50 where they agree, as a check. Settle our own differences, then report human vs human and human vs each LLM.
2. Write guide v3 from those decisions (mainly: when asking the user or stopping after an error counts as done).
3. No separate paid rerun on val, since tuning and measuring on the same items would inflate kappa. v3 is first measured on fresh items, the 3 recorded test passes, which have to be labelled anyway (about $2). If it reaches 0.7 there, those become the test labels.

Until then the turn end done check keeps training on the oracle labels, as before; the LLM labels only check them.

### Laya step check, first pilot (job 49656, `build_step_data.py`, `eval_step.py`)

Pooled call steps from our 9B runs and Shuban's 8B live steps (`pool_steps.py`), test scenarios dropped. Bad = breaks task, unneeded irreversible, or made up value on an irreversible call; wrong irreversible is left out (the LLM annotators flag only 7 to 10% of it). Train 8,847 calls (408 bad), dev 1,975 from 16 held out train scenarios (55 bad), val 2,427 (186 bad). Full finetune, one seed, 4 epochs, 16 min on one RTX 6000 Ada (mean GPU use 87%). A first job (49646) used labels that still counted wrong irreversible and was stopped after 12 min.

| Val part | calls | bad | rule "flag every irreversible call": AUROC / F1 | Laya finetuned: AUROC / F1 |
|---|---|---|---|---|
| all calls | 2,427 | 186 | 0.75 / 0.35 | **0.90 / 0.53** |
| irreversible calls only | 547 | 129 | 0.50 / 0.38 | **0.74 / 0.58** |
| reads only | 1,880 | 57 | 0.50 / 0.00 | **0.95 / 0.36** |

Laya as is: AUROC 0.57, F1 0.10. The gain holds on each source (9B 0.91, 9B reasoning on 0.83, 8B 0.93 AUROC) and within both parts the rule cannot split, so it is not only reading function names. One seed, threshold from dev; labels are the replay rules, not yet checked by people.

### Live step check on val, Laya against the 9B judge (jobs 49671, 49688, 49710, 49719, 49764; `rb_results.py`)

Mode rbh2dc (rollback plus done check, Shuban's best mode), Qwen3.5 9B agent (reasoning off), all 120 val tasks. Laya = finetuned step head (job 49656, dev threshold 0.204) plus done head (job 49265, 0.5). The 9B judge = the same 9B as SLM judge, reasoning on. About 2.3 GPU-hours on node01, never more than 2 GPUs at once.

| System | Pass | vs no judge [95% CI] | Tasks gained / lost | Steps | Interventions | Resamples |
|---|---|---|---|---|---|---|
| No judge (49274) | 43.3% | — | — | 13.9 | 0 | 0 |
| No judge, rerun (49146) | 43.3% | +0.0 [−6.7, +6.7] | +14 / −14 | 14.1 | 0 | 0 |
| Done check only (49274) | 45.8% | +2.5 [−5.0, +10.8] | +15 / −12 | 16.1 | 1.53 | 0 |
| Laya, gate bug (49671) | 37.5% | −5.8 [−11.7, +0.0] | +8 / −15 | 15.5 | 6.95 | 4.58 |
| **Laya, fixed (49719)** | **42.5%** | **−0.8 [−7.5, +6.7]** | +9 / −10 | 15.7 | 3.16 | 1.17 |
| 9B judge (49710, 49764) | 44.2% | +0.8 [−5.0, +7.5] | +11 / −10 | 14.6 | 2.66 | 1.73 |
| Oracle (49671) | 47.5% | +4.2 [−1.7, +10.8] | +11 / −6 | 16.3 | 6.34 | 3.55 |

- **The gate bug:** job 49671 used the done head as a gate on every closing message, so a flag threw the message away and resampled (4.6 per task). The head was trained only for the done check. Fixed in `dd90955`: closing messages pass the gate, and the done head answers only the done check. Resamples fell to 1.2 per task and the loss to −0.8.
- **No live system differs from no judge beyond noise.** The two no-judge runs score the same 43.3% but disagree on 28 of 120 tasks (+14 / −14). At this size, differences under about ±5 points cannot be told apart from run-to-run variation.
- **The ceiling is low on this agent:** even the oracle gives only +4.2 (CI includes 0), against +9.2 on Shuban's 4B. The 9B makes fewer mistakes that a step checker can fix.

**Offline per step, the same 1,277 val calls (109 bad, step labels of `build_step_data.py`):**

| Checker | Flags | Precision | Recall | F1 | AUROC |
|---|---|---|---|---|---|
| 9B judge (Q1 off track or Q2 flag) | 232 | 0.18 | 0.38 | 0.24 | 0.61 (yes/no) |
| **Laya, dev threshold** | 116 | **0.57** | **0.61** | **0.59** | **0.91** |
| Laya, top 232 (same flag count as 9B) | 233 | 0.36 | 0.78 | 0.50 | |

- Laya catches more than twice as many bad steps per flag as the 9B judge, from a 0.4B encoder with one forward pass per step. The 9B judge writes about 1,760 output tokens per call (80 s each at 96 at once) and 83 of 1,277 answers (6.5%) did not parse.
- The better offline checker does not yet turn into a live gain, because the room for gain on this agent (oracle +4.2) is within the noise of one 120-task run.

**Next:** (1) 3 seeds of no judge, Laya and the oracle on val, to bring the CI under the oracle's +4 (about 1 GPU-hour per system); (2) the same comparison on a weaker agent (Shuban's 4B, oracle +9.2), where a step checker has more to fix.

### Primary metric, off track half, on val calls (`primary_val_calls.py`, Shuban's `offline_eval.py` scorer)

Finetuned Laya step head (job 49656, dev threshold) against the 9B SLM judge (offline, reasoning on) on the 1,277 val calls, scored against the v2 annotator labels (calls kappa 0.73). Unparsed 9B answers (83) count as not flagged. CIs: bootstrap over the 15 val scenarios, paired for the difference.

| Labels | Off track | Laya F1 [CI] | 9B judge F1 [CI] | Laya − 9B [CI] |
|---|---|---|---|---|
| DeepSeek v2 | 45 | 0.42 [0.16, 0.60] | 0.28 [0.11, 0.46] | **+14.5 [+2.6, +20.3]** |
| GLM v2 | 44 | 0.36 [0.10, 0.55] | 0.24 [0.07, 0.44] | +11.8 [−0.7, +17.7] |
| Both agree | 33 | 0.39 [0.10, 0.58] | 0.23 [0.04, 0.45] | **+15.2 [+3.1, +21.6]** |

- Laya is ahead by 12 to 15 F1 points, above the proposal's 9 point bar, with the CI above 0 on DeepSeek and on both agree, and just touching 0 on GLM.
- Both judges find most of the off track calls (recall 0.66 to 0.82); Laya wins on precision (116 flags against 193).
- Caveats: val, not test; only 33 to 45 positives; Laya's head was trained on the replay labels, not on these; the false claim half is still missing for the 9B judge.

### Primary metric, both halves, on all 1,772 val steps (jobs 50247 and 50265, `primary_val.py`)

The 9B SLM judge, run with Shuban's `offline_eval.py --judge llm --reasoning on` (harness judge prompt, proposal state) on all 1,277 calls and 495 closing messages, 1 GPU, 41 min in all. The first pass (4,096 output tokens) left 328 steps without a verdict (reasoning ran out); `rejudge_unparsed.py` judged them again with 8,192 and 295 parsed, so 33 (1.9%) stay unparsed and count as not flagged. Mean output 1,500 tokens on a call and 2,380 on a closing message. Laya: the step head on calls, the done head on closing messages (P(not done) ≥ 0.5, the live threshold). Labels: v2 DeepSeek and GLM. CIs: paired bootstrap over the 15 val scenarios.

**As the proposal maps it** (Laya's "not done" = false claim, on track for Q1, as in the live runs):

| Labels | Laya primary | 9B primary | Laya − 9B [CI] |
|---|---|---|---|
| DeepSeek v2 | 0.18 | 0.19 | −1.0 [−7.3, +3.2] |
| GLM v2 | 0.19 | 0.17 | +2.0 [−5.4, +7.1] |
| Both agree | 0.19 | 0.18 | +0.5 [−6.7, +5.1] |

**Per class** (Laya's "not done" = off track for Q1 on closing messages):

| Labels | Q1 calls: Laya / 9B, diff [CI] | Q1 closing messages: Laya / 9B, diff [CI] | False claim: Laya / 9B (positives) |
|---|---|---|---|
| DeepSeek v2 | 0.42 / 0.34, +8.2 [−1.0, +13.5] | 0.52 / 0.34, **+18.0 [+3.3, +32.2]** | 0.07 / 0.05 (15) |
| GLM v2 | 0.36 / 0.29, +7.2 [−3.0, +12.8] | 0.42 / 0.28, +14.8 [−2.4, +31.7] | 0.10 / 0.05 (10) |
| Both agree | 0.39 / 0.29, +9.2 [−0.6, +15.2] | 0.47 / 0.34, +12.5 [−7.5, +33.4] | 0.07 / 0.06 (6) |

With this mapping the primary is Laya 0.20 to 0.24 against 0.17 to 0.19 for the 9B, +2.7 to +4.3 with CIs that include 0.

- **The primary hypothesis is not met on val.** Laya is ahead on off track for both calls and closing messages, by 7 to 18 points, but the primary averages that with false claim, where both judges sit near F1 0.05 to 0.10.
- **False claim cannot be measured on val:** the annotators find only 6 to 15 false claims among 495 closing messages. The proposal's test set is sized for 300.
- **Laya has no false-claim head:** its done head answers "done or not", so it calls 105 to 108 closing messages false claims against 6 to 15 real ones. Most "not done" turns are missing actions, which the proposal counts as off track, not false claims. A typed head that tells false claim from missing action is needed for Q2.
- **The 9B judge is stronger with Shuban's prompt:** on calls its F1 rose from 0.28 (`annotate.py` prompt) to 0.34, so Laya's lead on calls shrank from +14.5 to +8.2 against DeepSeek. This run is the fair SLM baseline, as it uses the harness judge prompt.

**Next:** (1) a Q2 head on closing messages trained to tell false claim from missing action and done; (2) the test labels (3 test passes, sized for 300 false claims), without which the false-claim half stays at a handful of positives.
