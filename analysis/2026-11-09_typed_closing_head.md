# Plan item 4.4: a typed closing-message head for Laya (fixed 9 Nov 2026, before any training)

**Status of this work.** A side experiment, added after the freeze of 8 Nov (`runs/ada/test_freeze.md`). The frozen
Laya (step head `orig_seed1` at 0.1266, done head `done_full_64348` at 0.561) stays the main system of the final
report, and the live runs (item 4.7) stay matched to it. This head is reported next to it, marked as a change after the
freeze.

**Why.** The primary metric is the mean F1 of off track and false claim. Laya's done head only answers done / not done,
and the proposal's scoring counts every "not done" as a false claim. On validation this gives false-claim F1 0.07 to
0.10 (105 to 108 flags against 6 to 15 real false claims) and no off-track flag on any closing message, so Laya ties
the 9B judge (−1.0 to +2.0) although it leads on tool calls (`analysis/2026-10-24_qwen35_9b_baseline.md`, mid report).
A head that separates "forgot a step" from "false claim" tests that explanation. The reason was found on validation
before any test run, and the mid report already planned it (timeline, 2 to 9 Nov).

Every choice below is fixed before training. Validation picks among the runs; the test set is scored once, after the
choice is written down.

| Choice | Value | Why |
|---|---|---|
| Training steps | The 3,737 closing messages of the 74 train scenarios of the 9B no judge run (job 49146), the done head's train and dev rows together | All closing messages of train scenarios; no fixed epoch choice needs a dev split |
| Input text | `build_done_data.py` `state_text`, as for the done head | Same input as the frozen head |
| Labels | DeepSeek V4.1 Flash and GLM-5.3-Flash, guide v3, `annotate.py --what turns` (same as the test labels); `runs/raw/test9b_labels/train/` | The automatic false-claim rule is not usable: the annotators agree with 4 of its 50 flags on validation, under the proposal's 80% rule |
| Classes | done; off track = `missing_action` or `should_ask_user`; false claim = `unsupported_claim` | The scoring map of `offline_eval.annot_label`, so the head's answer is the scored label |
| Target | Average of the two annotators' labels (a soft label); a row one annotator could not label uses the other | No choice of one annotator over the other |
| Model | Laya 0.3.27 typed decisions, revision `e929ae5`, one choice question with three options, full finetune | As the done head |
| Recipe | 2 epochs, batch 32, encoder lr 2e-5, head lr 1e-4, max length 1,024, option order shuffled per example, balanced class weights, last epoch kept; bf16 on the rented GPU | The done head's recipe (its best epoch was its last of 2); bf16 because that GPU supports it (Ada used fp16 only because the 2080 Ti does not) |
| Decision | false claim if P(false claim) ≥ t_fc; otherwise off track if P(off track) ≥ t_off; otherwise done | The scoring's order: a false claim is on track for Q1 |
| Thresholds | 5 folds of the 74 train scenarios, grouped by scenario (seed 0). Pooled out-of-fold probabilities; t_fc maximises the mean of F1 against DeepSeek and against GLM, then t_off on the rows not called false claim | The out-of-fold method of item 3.4; the 8 dev scenarios hold too few false claims |
| Seeds | 3 runs on all 74 train scenarios (seeds 0, 1, 2), each with the out-of-fold thresholds | As the step head |
| Choice of run | Highest validation primary (mean of DeepSeek v2, GLM v2 and both agree), with the frozen step head on calls, scored by `primary_val.py`'s method | As the frozen step head was chosen (best of 3 seeds). Validation labels are guide v2, the only complete set |
| Check before training | Laya as is on the done head's dev rows must match the Ada logs (AUROC 0.752) in this environment (torch 2.13, transformers 5.22) | The software differs from Ada |
| Test | After this choice is written down: frozen Laya, this head (with the frozen step head on calls) and the 9B judge on the 7,214 labelled test steps; primary with a paired bootstrap over the 100 test scenarios | The proposal's comparison |
| Not done | No live run with this head; the step head is unchanged | Time; the live result stays the frozen Laya's. A live run was added later, after the test scoring (section "Live run") |

## Results (9 Nov 2026)

Run on one rented 40 GB cloud GPU, after the 9B judge on the same machine. Outputs: `runs/raw/typed_head/`.
Scripts: `build_typed_data.py`, `train_laya_typed.py`, `typed_select.py`, `score_test.py`, `primary_test.py`, driven by
`runs/cloud/typed_auto.sh` and `typed_test.sh`.

**Training labels.** 3,737 closing messages, both annotators (2 messages with one label only). False claim: 182 by
either annotator, 56 by both. Off track (missing action or should ask): 630 by either, 293 by both.

**Environment check.** Laya as is on the done head's dev rows: AUROC 0.7512 here against 0.7524 on Ada (passed). Before
scoring test, each head was run on validation and compared with its saved scores: max difference 0.012 (frozen step
head), 0.006 (frozen done head), 0.029 (this head, bf16 in training against fp32 here).

**Deviations from the plan above.** None in the method. The runs went one at a time, not three, because three did not fit
in 40 GB; this does not change the results.

**Thresholds (out of fold on train):** t_fc 0.2601, t_off 0.4173 (out-of-fold F1 0.14 false claim, 0.48 off track).

**Validation (v2 labels; used to choose the run).** Primary, and the difference to the 9B SLM judge [95% CI]:

| | DeepSeek v2 | GLM v2 | both agree |
|---|---|---|---|
| 9B SLM judge | 0.19 | 0.17 | 0.18 |
| Laya frozen | 0.20, +0.5 [−8.6, +7.4] | 0.19, +2.2 [−7.0, +8.7] | 0.22, +3.8 [−6.8, +10.9] |
| typed seed 0 (chosen) | 0.34, +14.8 [+8.1, +21.7] | 0.27, +10.2 [+3.2, +17.8] | 0.30, +11.5 [+4.7, +19.0] |
| typed seed 1 | 0.32, +12.5 | 0.27, +10.1 | 0.28, +9.3 |
| typed seed 2 | 0.33, +13.9 | 0.28, +10.6 | 0.29, +11.2 |

**Test (7,214 labelled steps of the 8 test passes, guide v3 labels; scored once, after the choice).** Paired bootstrap
over the 100 test scenarios. 9B unparsed after the rejudge: 136 (1.9%). Positives in brackets.

| labels | system | off track F1 | false claim F1 | primary | − 9B [95% CI] | − Laya frozen [95% CI] |
|---|---|---|---|---|---|---|
| DeepSeek v3 | 9B SLM judge | 0.25 (1142) | 0.25 (91) | 0.246 | | |
| DeepSeek v3 | Laya frozen | 0.09 | 0.06 | 0.076 | −17.0 [−22.0, −11.2] | |
| DeepSeek v3 | Laya typed (after freeze) | 0.63 | 0.24 | 0.436 | +19.0 [+12.8, +24.8] | +36.0 [+28.6, +42.5] |
| GLM v3 | 9B SLM judge | 0.25 (1015) | 0.24 (76) | 0.245 | | |
| GLM v3 | Laya frozen | 0.10 | 0.06 | 0.078 | −16.7 [−22.0, −10.4] | |
| GLM v3 | Laya typed (after freeze) | 0.56 | 0.19 | 0.376 | +13.1 [+7.7, +18.6] | +29.8 [+23.6, +35.6] |
| both agree | 9B SLM judge | 0.23 (775) | 0.25 (49) | 0.240 | | |
| both agree | Laya frozen | 0.08 | 0.04 | 0.063 | −17.7 [−23.7, −10.4] | |
| both agree | Laya typed (after freeze) | 0.62 | 0.19 | 0.405 | +16.5 [+9.9, +22.8] | +34.2 [+26.7, +41.1] |

Off track by step kind (F1; 9B / Laya frozen / Laya typed): tool calls 0.21 / 0.28 / 0.28 (DeepSeek), 0.21 / 0.25 / 0.25
(GLM), 0.17 / 0.23 / 0.23 (both); closing messages 0.27 / 0.00 / 0.71, 0.28 / 0.00 / 0.65, 0.29 / 0.00 / 0.72.

**Reading.**
- **The primary hypothesis fails for the frozen Laya,** the system fixed before the test: it is 17 points below the 9B
  judge, with the CI below 0 on every label set. Most off-track positives in the test sample are closing messages
  (980 of 1,142 for DeepSeek), where the frozen Laya never says off track, and the 9B judge catches false claims far
  better on test (0.25) than on validation (0.05). On tool calls the frozen Laya still leads the 9B judge.
- **The typed head, built after the freeze and chosen on validation only, beats the 9B judge by 13 to 19 points,** with
  the CI above 0 on every label set: above the proposal's 9-point bar. The gain is off track on closing messages; false
  claim reaches the 9B judge's level (0.19 to 0.24 against 0.24 to 0.25).
- **Limits.** It is a change after the freeze, so it does not confirm the hypothesis; that needs fresh test data. It was
  trained on labels from the same two annotators (guide v3, train scenarios only) that grade the test, while the frozen
  Laya trained on the automatic labels. The test sample over-weights failed turns by the proposal's sampling rule; the
  F1 reweighted to the real mix of turns is still to do, as is the human check of 100 test steps. The live run
  below was added after the test scoring.
- **Weights** (fp16, 843 MB, sha256 `b702252020a0af5bb8205baec35cbaa83f5c5d275f2d59a227d30e4e2881d26e`) are kept outside git
  (`runs/raw/typed_head/typed_head_fp16.pt` locally), to go on a release.

## Live run (added 9 Nov 2026, after the test scoring, before the run)

Added after the offline test result above was known, so it is reported as a further check of the after-freeze head,
not as a confirmation. The frozen Laya's live result (item 4.7) stays the main live result. Fixed before the run:

| Choice | Value |
|---|---|
| System | `S_layastep@rbh2dc` (rollback plus done check), as the frozen Laya's item 4.7 run: frozen step head `orig_seed1` at 0.1266 on calls; this head at the done check (not done if false claim or off track by the decision rule above, t_fc 0.2601, t_off 0.4173); `analysis/laya_step_judge.py` with `LAYA_TYPED_WEIGHTS` |
| Tasks | Test split, 100 scenarios x 4 versions x 3 runs = 1,200 tasks (as item 4.7) |
| Setup | Qwen3.5 9B (`cyankiwi/Qwen3.5-9B-AWQ-4bit`, revision `e4d2d39c`), vLLM 0.27.1, reasoning off, the rented cloud GPU and server settings of the 8 no-judge passes (`runs/cloud/`), Laya in bf16 beside vLLM; `runs/cloud/live_typed.sh` |
| Baseline | The 8 no-judge passes on test (`runs/raw/test9b/`, 3,200 tasks): same software, harness and GPU type |
| Measure | Task pass rate; difference to the baseline with a 95% bootstrap CI over the 100 test scenarios (each scenario's pass rate over its versions and runs) |
| Also reported | Interventions per task; the frozen Laya's Ada result (+3.7 points over Ada's no-judge run) next to it, marked as a different GPU and serving setup |

### Live result (9 Nov 2026)

1,200 of 1,200 tasks, no harness errors, 73 minutes at 256 tasks at once (`runs/raw/typed_live/`). Pass rate, with
interventions per task in brackets; 95% bootstrap CI over the 100 test scenarios (`analysis/live_compare.py`):

| Version | No judge (8 passes, cloud) | Frozen Laya (Ada, item 4.7) | Typed head |
|---|---|---|---|
| base | 59.0 | 63.3 (1.36) | 63.3 (2.30) |
| miss_param | 39.9 | 39.7 (2.11) | 40.3 (3.41) |
| miss_func | 28.5 | 32.7 (3.11) | 33.3 (4.25) |
| long_context | 58.8 | 61.0 (1.39) | 62.0 (2.72) |
| **all** | **46.5** | **49.2** (1.99) | **49.8** (3.17) |

- **Typed head − no judge: +3.2 points [+0.4, +6.2].** The CI is above 0.
- **Typed head − frozen Laya: +0.6 [−2.0, +3.2]**, so no difference. The frozen run is on Ada (2080 Ti, fp16) and
  this one on the cloud GPU (bf16); against the cloud no-judge passes the frozen Laya gives +2.6 [−0.2, +5.6].
- The typed head sends the agent back more often (3.17 against 1.99 interventions per task; 2.38 "not done" per task),
  as expected from a head that now also flags off-track closing messages. Its far better offline detection (+16.5 over
  the 9B judge, both agree) turns into about the same live gain as the frozen head: both sit near the validation
  oracle ceiling of about +4, so the limit is the agent's ability to fix what it is told, not the check.
