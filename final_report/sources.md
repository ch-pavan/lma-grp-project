Number to source map for the final report. Paths are relative to the repo after `pavan/test-results` is merged into `main`.

| Report item | Source |
| --- | --- |
| Live test on Ada: 45.5 / 49.2 / 49.2 / 55.8, gains +3.7 [+0.8, +6.8], +3.7 [+1.1, +6.5], +10.3 [+7.0, +13.8], Laya − judge +0.0 [−2.8, +2.9] | analysis/rb_test_results.py; docs/phase_plan.md item 4.7 |
| Per version pass rates, seconds per task (426, 528, 1,621, 691), judge tokens per task (52,672), interventions | final_report/scripts/live_cost.py runs/raw/q9b_test |
| Typed head live 49.8%, +3.2 [+0.4, +6.2], 3.17 vs 1.99 interventions, per version | analysis/live_compare.py; analysis/2026-11-09_typed_closing_head.md "Live result" |
| No judge on test, 3,200 tasks: 46.5% [40.4, 52.8], calls, closing messages, done turns | runs/raw/test9b/test/summary.json, runs/raw/test9b/oracle_labels.log |
| Failure types (24.8, 24.3, 16.8, 15.3, 14.7, 2.7 + 1.3) | runs/raw/test9b/oracle_labels.log |
| Test sample 7,214 steps (5,171 calls, 2,043 closing messages), positives, primary table, per kind F1 | runs/raw/typed_head/primary_test.md (analysis/primary_test.py) |
| 9B judge unparsed after rejudge: 136 (1.9%) | analysis/2026-11-09_typed_closing_head.md |
| Typed head recipe, thresholds 0.2601 / 0.4173, training label counts, seeds on validation (+14.8 / +12.5 / +13.9 …) | analysis/2026-11-09_typed_closing_head.md; runs/raw/typed_head/select/; runs/raw/typed_head/select.log |
| Annotator agreement on test (kappa 0.565 calls, 0.550 three classes, 0.568 false claim) | final_report/scripts/test_agreement.py runs/raw/test9b_labels |
| Frozen heads (orig_seed1 at 0.1266, done head at 0.561), 8B test 13.5% and its pairings, validation done modes, context rerun | runs/ada/test_freeze.md |
| Test baselines S1 15.9, S2 7.6, S3 17.4, Laya as is, Granite, AgentDojo 33.7 / 18.2 / 25.8 | shuban_findings/results/test_baselines.md, shuban_findings/findings.md |
| Agent models 25.8, 40.0, 43.3, 36.7, 52.7 | shuban_findings/findings.md, analysis/2026-10-24_qwen35_9b_baseline.md |
| Offline judges table | shuban_findings/results/offline_judges_9b_val.md |
| Validation step and done check (AUROC 0.91 / 0.61, F1 0.59 / 0.24, done AUROC 0.79 / 0.59 / 0.53, F1 0.53 / 0.41), live validation table, primary on validation | analysis/2026-10-24_qwen35_9b_baseline.md; analysis/primary_val.py |
| Correction actions (forest figure) | shuban_findings/results/val_correction_modes.md |
| Phase 3 reruns (breaks task, seeds, done threshold) | analysis/2026-10-31_step_nobt_and_done_cv.md |
| Rules vs Laya on v2 labels | analysis/2026-10-30_rules_vs_laya_v2.md |
| Human check kappa 0.84 / 0.71, guide versions | analysis/2026-10-30_guide_v3.md; human_check/val2/results_v3.md |
| Gate 1 counts 310 / 372 / 217 / 143 | analysis/2026-10-25_status_and_benchmarks.md; mid report |
| Figures 1 to 5 and 10 | mid_submission/condensed/figs/ (copied) |
| Figures 6 to 9 (typed seeds, live test, primary on test, failures) | final_report/make_figs.py, numbers as listed above |
