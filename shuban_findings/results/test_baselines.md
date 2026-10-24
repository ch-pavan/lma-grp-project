# BFCL multi turn baselines (Stay on Task)

Agent: Qwen3 8B AWQ planner and doer on vLLM 0.19.1, one RTX 2080 Ti per run, thinking off for the agent, on for the S3 judge. Test set: 100 held out scenarios (sha256 split, 11 unsound scenarios dropped) in 4 versions (base, miss_param, miss_func, long_context), 3 runs each. Pass = BFCL state checker plus our empty turn check (any state change on a turn whose gold is empty fails it). CIs are 95% bootstrap over scenarios. Chart: summary.png. Raw numbers: summary.json.

| System | Runs | Pass % [95% CI] | vs S1, points [95% CI] | Blocks per task | Steps per task | s per task | Tokens per task (judge) |
|---|---|---|---|---|---|---|---|
| S1 no judge | 1200 | 15.9 [11.7, 20.5] | | 0 | 9.8 | 93 | 63.5k (0) |
| S2 plain rules | 1200 | 7.6 [4.4, 11.2] | -8.3 [-11.8, -5.2] | 4.0 | 10.8 | 108 | 64.9k (0) |
| S3 Qwen3 8B judge, reasoning on | 1200 | 17.4 [12.8, 22.3] | +1.5 [-0.6, +3.8] | 1.8 | 10.4 | 202 | 78.0k (11.8k) |
| S4a Laya typed decisions as is | 133 (stopped) | 0, exact upper bound 2.2 | | 18.7 | 21.1 | 336 | 94.0k |
| S4b Granite Guardian 3.2 3B A800M | 223 (stopped) | not valid, see below | | 2.7 | | 2415 | |

Per version pass rate (base, miss_param, miss_func, long_context): S1 27.0, 16.3, 8.7, 11.7. S2 12.0, 8.0, 3.7, 6.7. S3 26.0, 19.3, 16.0, 8.3.

S3 is the only judge that does not hurt. It gains most on miss_func (+7.3) and miss_param (+3.0), the versions where the right move is to ask instead of act. The overall gain is inside the noise and costs about twice the time per task.

S2 blocks good calls too often. On a gold replay of every kept task its made up value rule still flags 1.8% of gold calls, and on live runs a call missing from the plan counts as drift.

S4a was stopped after 133 runs that cover all 100 scenarios once (base 100, miss_param 33). Laya blocked 2482 of 2833 judged steps (87.6%), so every run hit the 20 step cap. Its vs S1 difference is left out because it ran on base and miss_param only.

S4b was stopped after 223 runs (all 100 scenarios: base 100, miss_param 100, miss_func 23). It passed 0, but 117 of those runs ended in a timeout from the Granite server on the second card (600 s per call), so the 0 measures the serving setup, not the judge. It blocked 593 of 1053 judged steps (56.3%). A rerun gave Granite only the called tool's doc and scored it on CPU in the same job (one 2080 Ti cannot hold both models in fp16). Pilot of 20 tasks: no timeouts, 0 passed. Granite answered Yes (risky call) on all 169 calls it saw and flagged none of 52 closing messages, so 76.5% of judged steps were blocked. That is over the 50% stop rule, so this is Granite's result: as is, it treats every BFCL call as a risky function call. Data: pilot_g2/S4b_granite.

Speed (one 2080 Ti): cold prefill 3,700 tok/s; a 6k prompt with 5k cached takes 0.33 s. Decode per stream / total tok/s: 80/80 at 1 stream, 44/350 at 8, 11/262 at 24. KV room 2.0 to 2.44 GiB (14.5k to 17.8k tokens) depending on the node.

## AgentDojo benign user tasks

97 user tasks (workspace 40, travel 20, banking 16, slack 21), no injections, agentdojo 0.1.35 with suites v1.2.2, 3 runs each, pass = the task's own utility check. Same harness, model and judges as above. Chart: ../results_ad/summary.png.

| System | Runs | Pass % [95% CI] | vs S1, points [95% CI] | Blocks per task | s per task | Tokens per task |
|---|---|---|---|---|---|---|
| S1 no judge | 291 | 33.7 [25.4, 42.3] | | 0 | 16 | 18.9k |
| S2 plain rules | 291 | 18.2 [12.0, 25.4] | -15.5 [-22.7, -8.6] | 5.9 | 13 | 31.7k |
| S3 Qwen3 8B judge | 291 | 25.8 [18.2, 33.7] | -7.9 [-13.1, -3.1] | 2.6 | 78 | 33.4k |

Per suite (workspace, travel, banking, slack): S1 30.8, 18.3, 45.8, 44.4. S2 18.3, 1.7, 29.2, 25.4. S3 25.0, 10.0, 41.7, 30.2.

Out of domain the LLM judge hurts: it blocks 2.6 steps per task and 22 of its 291 runs hit the step cap (S2: 71). On BFCL it was neutral to slightly positive. Ground truth replay through the harness passes 97 of 97 tasks with no judge, so the losses are judge blocks, not harness errors (2 to 4 runs per system ended in an API error).

## Offline judges on recorded BFCL steps

Kev 0.8B (jaredpalmer/kev-0.8b, same Q1 and Q2 typed questions as Laya) on every call and closing message, LettuceDetect v2 (KRLabsOrg/lettucedect-v2-mmbert-base) on closing messages against that turn's tool outputs. 200 episodes per system, half passed and half failed, picked in sha256 order of id and run. Run on the laptop GTX 1650 (also sm75, Kev runs in fp16 there at about 2 s per step). Data: ../offline/.

| System | Judge | Steps judged | Steps flagged % | Tasks with a flag, passed / failed % | AUROC of max flag prob vs task failure |
|---|---|---|---|---|---|
| S1 | Kev | 2014 | 76.4 | 100 / 97.0 | 0.55 |
| S1 | LettuceDetect | 793 | 25.6 | 54.0 / 65.0 | 0.54 |
| S2 | Kev | 2080 | 73.5 | 98.9 / 97.3 | 0.63 |
| S2 | LettuceDetect | 784 | 37.4 | 58.2 / 69.5 | 0.48 |
| S3 | Kev | 2092 | 75.5 | 100 / 98.0 | 0.53 |
| S3 | LettuceDetect | 892 | 33.3 | 65.0 / 77.9 | 0.51 |

Neither separates passed from failed tasks: AUROC sits at chance and Kev flags three quarters of all steps, in line with its own card's warning against tool call routing. LettuceDetect flags failed tasks a little more often, but its context is the tool output as logged, cut at 300 characters, which can make true claims look unsupported. S4a and S4b are left out, they have no passed tasks to compare against.
