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
