# Stay on Task: phase-wise plan from 30 Oct 2026

The goal is to make every statement in the repo and the mid-submission report true and checkable, then finish the project.

Each task gives:
- **What:** the change.
- **Why:** the problem it fixes. "Check #n" refers to `midreport-check.md`.
- **Done when:** a test anyone can run.
- **Owner.**

## Ground truth this plan works from

| Topic | What is true |
|---|---|
| Annotation | Two LLM annotators label the steps: **Annotator A = DeepSeek V4.1 Flash**, **Annotator B = GLM-5.3-Flash**. They run through `analysis/annotate.py` on the OpenCode API. Every row of their label files records the model. |
| Annotation check | **Swayam Goyal and Aaditya Sharma** cross-check the LLM labels. Each labels the stratified check sample blind, and **Ch Pavan Harshit** referees their disagreements. |
| Proposal baseline | `proposal/proposal.md` (revised, 24 Oct) already says "labels from the two LLM annotators, checked by hand on a subset". Proposal v5, the PDF, said hand labels only. |
| Numbers | Every table in the mid report reproduces from the repo scripts, per `midreport-check.md`. The problems are attribution, caveats and wording, not data. |

## Decisions (30 Oct 2026)

| # | Decision | Outcome |
|---|---|---|
| D1 | Which proposal is the baseline? | **The revised `proposal/proposal.md`.** The v5 to revision changes are listed separately. |
| D2 | Who referees the check disagreements, and who did the 7-step second pass? | **Pavan referees; Shuban did the second pass.** |
| D3 | Do fixes rewrite commits or land as new ones? | **New commits:** 30 for the repo attribution fixes, 31 for the corrected report. No force-push. |
| D4 | Relabel all 1,772 validation steps with guide v3? | **Deferred.** Training uses oracle labels, not LLM labels, so it isn't needed for training. It is a validation-only redo of the v2 job: about 3,140 calls, about $1, about the same as the v2 run. The report states that full-validation labels are still v2. Revisit at Phase 4, together with the test labelling, which is required. |

## Status

| Phase | Status |
|---|---|
| 1. Attribution | **Done.** Commit 30 covers 1.1 to 1.3. Items 1.4 and 1.5 are in the report, commit 31. |
| 2. Report wording | **Done.** Commit 31: all 13 items from `midreport-check.md`, plus 16 more from a second fact-check. |
| 3. Data gaps without GPUs | **Next.** 3.1 and 3.2 are deferred (D4). |
| 4. GPU experiments | From 1 Nov |

**Second fact-check, key corrections:**
- **Off-track result.** Under the proposal's scoring, Laya trails the 9B judge on off-track F1 over all steps (0.27 to 0.30 against 0.29 to 0.34). It leads only on tool calls, by +7 to +9 points.
- **Training labels.** The step head still trains on the oracle off-track rule ("breaks task", 276 of 408 bad training calls), which failed the 80% agreement rule. This is now Phase 3 item 3.7.
- **Gate 1 counts.** Pooled over the 9B and 8B steps: off track 310 and false claim 372 pass; unneeded irreversible 217 and made-up values at most 143 do not.
- **Baselines.** The test baselines used the Qwen3 8B agent and judge, so they must be rerun with the 9B for the task claim. This is now Phase 4 item 4.9.
- **Rules comparison.** Table 10 was scored against v1 labels, so rules and Laya are not comparable yet. This is now Phase 3 item 3.8.

## Phase 1: make the attribution true (no new runs)

| ID | What | Files | Done when |
|---|---|---|---|
| 1.1 | Name the annotators as the LLMs they are: "Annotator A (DeepSeek V4.1 Flash)" and "Annotator B (GLM-5.3-Flash)" | `human_check/score.py` (display names), `human_check/README.md`, `analysis/2026-10-30_guide_v3.md`, `mid_submission/mid_report.tex`, `mid_submission/make_figs.py` (figure 6 legend) | Searching the repo finds no "Swayam (Annotator A)" or "Aaditya (Annotator B)" |
| 1.2 | Credit the check to its labellers: rename the check sheets to `labels_swayam.csv` and `labels_aaditya.csv`, with Pavan as referee | `human_check/{pilot,val2}/labels_*.csv`, `decisions.csv` (columns and notes), `human_check/README.md` roles table, guide v3 write-up | `score.py` prints "aaditya vs swayam" and the decision notes name Pavan |
| 1.3 | Regenerate every results file | `human_check/{pilot,val2}/results*.md`, `consensus.csv` | Numbers identical to now; only names change |
| 1.4 | Fix the roles table in the report: Swayam and Aaditya do annotation checking and guide v3, Pavan does refereeing and runs, Shuban does the harness and baselines | `mid_report.tex` Table 2 | Matches 1.1 and 1.2 |
| 1.5 | Name the proposal baseline (D1) in the report, and split "changes from the proposal" into v5 to revision and revision to now | `mid_report.tex` section 13 | Check #8 closed |

## Phase 2: correct the mid report wording (no new runs)

| ID | Check | Fix |
|---|---|---|
| 2.1 | #2 | Abstract: "LLM labels for every validation step (guide v2), plus a 200-step human check; only the 200 checked steps have v3 labels so far." |
| 2.2 | #3 | Table 15 decision column: "0.6 to 0.8 band: label more steps (passes the 0.7 bar)". Add the same to figure 6's caption. |
| 2.3 | #4 | Use the fresh-sample numbers as the headline (A 0.71 to 0.84, B 0.66 to 0.71). Mark the 200-step row "includes the pilot v3 was written from, optimistic". |
| 2.4 | #5 | Done check: lead with AUROC 0.79 against 0.53. Give F1 at both thresholds: 0.53 at 0.5, and 0.36 at the dev-chosen 0.98 against 0.41 for the 9B. Say the comparison depends on the threshold. |
| 2.5 | #6 | Step check headline: state its conditions. The 9B used the v1 annotator prompt, 83 unparsed answers count as "not flagged", and the labels follow the training rule. Add the fairer comparison: harness prompt and annotator labels, a lead of about +8 points. |
| 2.6 | #7 | "Rollback plus the done check moved results with the oracle on Qwen3.5 4B (+9.2 [+2.5, +15.8]); borderline on Qwen3 8B (+5.8 [0.0, +12.5])." Drop "the only lever". |
| 2.7 | #9 | Add a caveat: the checkers labelled val2 with the first v3 draft. Rules 1 and 2 were reversed afterwards, and no val2 label depends on them. Mention the 7 contested pilot steps and the 0.57 / 0.78 sensitivity. |
| 2.8 | #10 | List rule 3 (self-chosen values need asking) as "kept, contested". |
| 2.9 | #11 | Add the annotator-vs-annotator column: 0.66, 0.66, 0.73, 0.76. |
| 2.10 | #12 | No change. The check is wrong here: `score.py` compares the raw sheets before refereeing. |
| 2.11 | #13 | Note that false claims are half the primary metric. |
| 2.12 | Gate 1 | State it plainly: no step class reaches 300 training examples (off track 221, false claim 281). The 672 unfinished turns are not a proposal class. |
| 2.13 | Coverage | List the proposal items not started: escalation, calibration, AgentProcessBench and AgentHallu, the stronger reference judge, Laya alone and the full system online. |

**Phase 2 is done when** a fresh fact-check of the rebuilt PDF finds no wrong or overstated claim.

## Phase 3: close data gaps without GPUs (API and CPU only)

| ID | What | Why | Done when | Owner |
|---|---|---|---|---|
| 3.1 | Deferred (D4): relabel all 1,772 validation steps with guide v3 | Check #2: the full-validation labels are still the failed v2 | For now, the report states the labels are v2 | Pavan |
| 3.2 | Only if 3.1 runs: rerun the primary metric against the v3 labels | The current primary uses v2 labels | New Table 13 with paired CIs | Pavan |
| 3.3 | Score the step check against annotator labels with the harness-prompt 9B, unparsed answers reported separately | Check #6 | A table of Laya against 9B with CIs on A, B and both-agree labels | Shuban |
| 3.4 | Done check: report AUROC and F1 at the dev threshold, and choose thresholds by grouped cross-validation on train | Check #5 | Threshold fixed before any validation look | Pavan |
| 3.5 | Gate 1 table: training counts per proposal class | 2.12 | Table in the report | Swayam |
| 3.6 | Rebuild the report with Phases 1 to 3 and run the fact-check again | All | Zero open items | Swayam, Aaditya |
| 3.7 | Retrain the step head without the oracle "breaks task" label, or on annotator-checked labels, and compare | The label failed the 80% rule but is set on 276 of 408 bad training calls | Step check reported with and without it | Pavan |
| 3.8 | Score the rules and Laya against the same LLM labels (v2, and v3 where available) | Table 10 used v1 labels; rules and Laya are not comparable | One per-question table | Shuban |

## Phase 4: the experiments the proposal still needs (GPU from 1 Nov)

| ID | What | Done when | Owner |
|---|---|---|---|
| 4.1 | 9B test passes, until 300 false claims or 8 passes. The stop rule is fixed before seeing results. | Recorded steps for 400 tasks per pass | Pavan |
| 4.2 | LLM annotation of the test steps with guide v3 | `annot_v3_*` for the test steps | Pavan |
| 4.3 | Human check of 100 test steps: Swayam and Aaditya label, Pavan referees | Results for the test sample, kappa against both annotators | Swayam, Aaditya, Pavan |
| 4.4 | A typed closing-message head for Laya, with a false-claim class | False-claim F1 on validation above the 9B judge, then frozen | Pavan |
| 4.5 | Primary metric on test: paired bootstrap, Holm correction | The hypothesis is confirmed or falsified | Shuban |
| 4.6 | Ablations: state parts (no plan, no recent calls, no evidence list), escalation budget, 3 seeds | Ablation table | Shuban, Swayam |
| 4.7 | Online test runs with rollback and the done check, plus a 4B pilot | Task accuracy with CIs | Pavan, Aaditya |
| 4.9 | Rerun the test-set baselines (no judge, rules, SLM judge) with the Qwen3.5 9B agent and judge | The current test baselines used Qwen3 8B | Table 9 on the 9B | Pavan, Shuban |
| 4.8 | Optional, if time allows: AgentProcessBench and AgentHallu any-flag F1, and Gemma 4 12B as a reference | Results, or listed as future work | Shuban |

## Phase 5: final submission

Final report, release of the LLM and human-check labels, and repo clean-up. Every number comes from a script in the repo, and the final PDF gets the same fact-check.

## Rules for every phase

- **Reproducible numbers only.** A number goes into a report only if a repo script reproduces it. Caveats from the write-ups travel with their numbers.
- **One baseline proposal.** Each change says which proposal it is measured against.
- **Fixed before looking.** Thresholds, stop rules and mappings are fixed before test data is touched.
- **History is safe.** Old outputs move to the local old files folder; nothing is deleted.
