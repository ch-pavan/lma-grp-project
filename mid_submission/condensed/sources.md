Number to source map. Paths are relative to the repo clone lma-grp-project at commit e0d1b64. Numbers carried over unchanged from the team draft (orig/mid_report.tex) were re checked against these files.

| Report item | Source |
| --- | --- |
| Test baselines S1 15.9, S2 7.6, S3 17.4, Laya as is 0 of 133, Granite pilot, AgentDojo 33.7 / 18.2 / 25.8 | shuban_findings/results/test_baselines.md, shuban_findings/findings.md |
| Agent models 25.8, 40.0, 43.3, 36.7, 52.7 | shuban_findings/findings.md, analysis/2026-10-24_qwen35_9b_baseline.md |
| Failure types of the 9B (26.5, 23.5, 22.1, 17.6, 8.8) | analysis/2026-10-24_qwen35_9b_baseline.md |
| Offline judges, primary F1 ranges (Table 6) | shuban_findings/results/offline_judges_9b_val.md, laya_tuning.md |
| Done check AUROC 0.53 / 0.59 / 0.79, F1 0.53, 0.36 at dev threshold 0.98 (line 159), 9B judge 0.41 | analysis/2026-10-24_qwen35_9b_baseline.md lines 150 to 175 |
| Step check P/R/F1/AUROC 0.18/0.38/0.24/0.61 against 0.57/0.61/0.59/0.91 | same file, lines 235 to 241 |
| Live table (Table 7) | same file, lines 161 to 174 and 219 to 227 |
| Primary metric table (Table 8), lead +8.2, +7.2, +9.2 | same file, lines 250 to 285 |
| Correction modes and forest rows for Qwen3 8B and Qwen3.5 4B | shuban_findings/results/val_correction_modes.md |
| Rules against Laya on v2 labels (0.07/0.06 against 0.18/0.19) | analysis/2026-10-30_rules_vs_laya_v2.md lines 109 to 120 |
| Kappa table (Table 10), 7 contested steps, 0.42/0.60 to 0.57/0.78, false claim kappa 0.46 / 0.38 | analysis/2026-10-30_guide_v3.md lines 9 to 14, 66 to 146 |
| Gate 1 counts 310 / 372 / 217 / 143 | analysis/2026-10-25_status_and_benchmarks.md |
| Owners and plan items | docs/phase_plan.md lines 88 to 104 |
| Train sizes 8,847 calls (408 bad), 3,341 turn ends, 16 and 5 minutes, 276 of 408 breaks task | team draft orig/mid_report.tex lines 321, 453, 643 (analysis/ Laya finetune notes) |
| Timeline dates | made for this report, ends 15 Nov 2026, evaluations 16 to 19 Nov |
