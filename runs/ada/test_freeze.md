# Laya on the original BFCL test: choices fixed before the run (8 Nov 2026)

Team decision (7 Nov): finetuned Laya is run as one more system in Shuban's original test baselines
(`shuban_findings/results/test_baselines.md`), so the existing no judge, plain rules and Qwen3 8B judge rows stay the
comparison and need no rerun. Where to go next is decided from the results.

Everything below was fixed from train and dev data only, before any test task was run with finetuned Laya.

| Choice | Value | Why |
|---|---|---|
| Setup | `run.py` plain block mode, Qwen3 8B AWQ agent, vLLM 0.19.1 (Shuban's `pins.txt`), 20,480 token context, `--max-num-seqs 32`, concurrency 10, gorilla `6ea5797`, test split of `split.json`, 4 versions, 3 runs | Identical to the S1, S2 and S3 test rows |
| Step head | Ada rerun `orig_seed1` (job 49477, original labels), threshold 0.1266 | Best of the 3 seeds on dev (AUROC 0.972, F1 0.59); the threshold is its dev threshold |
| Done head | Full finetune on the train split with the cross-validation recipe (2 epochs, fp16, seed 0), job `laya_done_full.sbatch`, threshold 0.561 | 0.561 is the out-of-fold threshold of item 3.4, chosen without validation |
| Closing messages | Judged once by the done head (`LAYA_GATE=0`); P(not done) at or above 0.561 blocks with run.py's false claim warning | Plain mode asks about a closing message once, as for S3 |
| Calls | Step head; P(bad) at or above 0.1266 blocks with run.py's off track warning | As for S3 |
| Hardware | 2 RTX 2080 Ti per job: the agent server on the first exactly as in `run_body.sh` (memory use 0.88), the Laya heads in fp16 on the second | Both heads do not fit next to the server at 20,480 tokens on one 11 GB card |
| Order | Pilot on 2 scenarios (8 tasks), then the full run in 3 shards | |

Every step's judge input is recorded (`states_S_layastep.jsonl`), so the same steps can later be labelled for the F1
comparison.

## What happened after the freeze (8 Nov, night)

- **Done head.** Job 64348 (gnode055, 9 min): best epoch 2, dev AUROC 0.826, val AUROC 0.754.
- **Context.** On gnode055 the server did not fit 20,480 tokens at memory use 0.88 and, by the same fallback as
  `run_body.sh`, started at 16,384. The baselines ran with the same script, so the same fallback applied to them.
- **Pilot, job 64349** (test scenarios 0 and 3, 4 versions, 1 run, 8 tasks): 0 of 8 passed. 5 hit the 20 step cap.
  The done head blocked 109 of 126 closing messages: plain mode judges every retry again, so once a turn is flagged
  "not done" the agent's next messages are flagged too. The step head blocked 20 of 36 calls, mostly repeats of one call.
- **Heads are not broken.** Job 64372 scored both heads through the same code and environment: step head val AUROC
  0.885 (as in training), 6.4% of val calls flagged; done head val AUROC 0.753, 14.3% of val closing messages flagged;
  fp16 and fp32 agree. The judge input on test steps has the training format.
- **Next.** The frozen design runs on the full test anyway (jobs 64380 and 64381), so its result exists as fixed.
  Three ways of handling closing messages run on **validation only**, for the team to choose from: `block` (frozen),
  `once` (at most one block per turn, like the done check) and `off` (step head only), plus no judge through the same
  harness (jobs 64382 to 64385). Any change chosen from these is a change after the freeze and is reported as one.

## Results (8 Nov, morning)

Raw outputs: `runs/data/laya_test/test_runs/` (local). Pass rates from `shuban_findings/code/analyze.py`, 95% bootstrap
CIs over scenarios.

**Test, frozen design (jobs 64380 and 64381, 1,200 tasks): 13.5% [9.7, 17.8].** Paired with Shuban's task logs
(release `shuban-logs-2026-11-07`, same `split.json`, same 1,200 tasks, bootstrap over the 100 scenarios):

| Against | Difference | Tasks gained / lost |
|---|---|---|
| S1 no judge (15.9) | −2.4 [−5.2, +0.2] | +64 / −93 |
| S3 8B judge (17.4) | −3.9 [−7.1, −1.1] | +65 / −112 |

Laya does not beat no judge (the CI includes 0, leaning negative) and is below the 8B judge (the CI excludes 0).

| Version | Laya, frozen | S1 no judge | S2 rules | S3 8B judge |
|---|---|---|---|---|
| base | 20.3 | 27.0 | 12.0 | 26.0 |
| miss_param | 15.0 | 16.3 | 8.0 | 19.3 |
| miss_func | 9.3 | 8.7 | 3.7 | 16.0 |
| long_context | 9.3 | 11.7 | 6.7 | 8.3 |
| **all** | **13.5** | **15.9** | **7.6** | **17.4** |

**What the judge did on test:**
- **Closing messages.** The done head blocked 78% of them (11,151 of 14,252). 596 of the 1,200 tasks hit the 20-step
  cap, with 9 fresh doers per task.
- **Calls.** The step head blocked 15.2% of calls (997 of 6,549). On labelled validation calls it flags 6.4%.

**Context rerun (jobs 64483 and 64484).** The test jobs ran at 16,384 tokens, so long_context was rerun at the frozen
20,480, with the agent server retried at the same length (`KEEPLEN=1`). The result was 8.3% (against 9.3%), or 13.2%
[9.4, 17.6] with the other three versions. Both runs had 79 context overflows, 74 of them on the same tasks. These come
early (3.6 steps, 0.15 blocks on average): those long_context prompts exceed 20,480 tokens from the start, and no judge
hits the same tasks (4 of 30 on validation). The fallback therefore made no difference, and 13.5% stays the reported
number. Shuban's logs show the same fallback in the baselines: S1 ran at 16,384 (75 overflows), S3 at 20,480 (73
overflows), and S2 at 20,480 (35, since its tasks often end at the step cap first).

**Validation variants (15 scenarios, 2 runs, 120 tasks each).** All ran through the same harness at 20,480 tokens. The
difference to no judge is paired over scenarios.

| Closing messages | Pass | vs S1 no judge | Closing messages blocked | Calls blocked | Steps per task |
|---|---|---|---|---|---|
| S1 no judge | 22.5 [9.2, 37.5] | | | | 10.4 |
| `block` (frozen) | 12.5 [3.3, 24.2] | −10.0 [−20.8, −0.8] | 77% | 18.4% | 17.6 |
| `once` | 17.5 [5.8, 30.8] | −5.0 [−13.3, +1.7] | 21% | 16.1% | 11.6 |
| `off` (step head only) | 18.3 [7.5, 30.8] | −4.2 [−8.3, +0.0] | 0% | 11.8% | 10.2 |

**Reading.** In plain block mode, finetuned Laya is below no judge on test and on validation. The main loss comes from
the done head: every retry of a flagged closing message is judged again, so the turn runs into the step cap. Neither
closing-message variant beats no judge on validation, and neither does the step head alone, so no post-freeze design was
run on test.
