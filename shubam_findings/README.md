# Baseline and judge experiments (Shuban)

Independent test runs for Stay on Task. Read findings.pdf first.

- findings.pdf, findings.md: what we found so far, with a section for the finetuning work.
- finetune_data/: oracle labelled agent steps from BFCL train and val scenarios, ready for training a step judge. See its README. Test scenarios are held out, keep them out of training.
- results/: test set baselines (BFCL and AgentDojo), the validation table of every correction mode and judge, and the Laya tuning table.
- code/: the harness (planner, doer, judges, correction modes, oracle, analysis) and the Ada job scripts. Agents run on vLLM 0.19.1 on RTX 2080 Ti.

Final test runs of the best modes are running; results/ gets updated when they land.
