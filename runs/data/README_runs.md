# Run data, 24 Oct 2026 (Qwen3.5 9B agent on BFCL multi turn, Shuban's harness)

Write-up: analysis/2026-10-24_qwen35_9b_baseline.md in the repo.

In git (29 Oct 2026): the raw run outputs live in runs/raw/; the files made from them (labels, annotator outputs, Laya datasets, Laya val scores, 9B judge predictions) are tracked here as .jsonl.gz. Run `sh runs/unpack_data.sh` from the repo root to rebuild this folder with plain .jsonl, as the analysis scripts expect. Not in git: the .tar.gz bundles (same content) and Laya weights (0.1 to 1.6 GB; retrain with runs/turing/laya_*.sbatch).

## q9b_s1t_49146.tar.gz (job 49146, no judge, S1_record)
- val/ (120 tasks, reasoning off), val_think/ (120 tasks, reasoning on), train/ (888 tasks, reasoning off)
- Per folder: tasks_*.jsonl (one row per task), steps_*.jsonl (step log plus decoded calls), states_S1_record.jsonl
  (every step's judge input, proposal state layout), split.json
- Added offline: labels.jsonl (per step: off_track_suffix, off_track_subset, false_claim, done at turn end),
  turns.jsonl (per turn: done, missing functions, failure type) from analysis/oracle_labels.py;
  step_labels.jsonl (unneeded or wrong irreversible, made up value, breaks task) from analysis/step_labels.py
- val/annot_deepseek.jsonl, val/annot_glm.jsonl: DeepSeek V4.1 Flash and GLM-5.3-Flash labels for all val turn ends and calls
- gold_steps.jsonl: gold replay check (755 of 756 pass)

## q9b_dc_49274.tar.gz (job 49274, live done check on the 120 val tasks)
- S1_none, S_layadone@dc (finetuned Laya), S3_llm_judge@dc (9B SLM judge), S_oracle@dc; offline_9b_judge.jsonl

## laya_done.tar.gz
- train/dev/val turn end rows used to finetune Laya (analysis/build_done_data.py)

## laya_runs/ada_step_nobt/ and laya_runs/ada_done_cv/ (Ada, 31 Oct 2026, plan items 3.7 and 3.4)
- ada_step_nobt/{nobt,orig}_seed{0,1,2}: step head without and with the oracle "breaks task" label, fp16 on an RTX 2080 Ti
  (runs/ada/laya_step_nobt.sbatch, jobs 49477 and 49597); results.json, val_scores.jsonl.gz, train.log
- ada_done_cv/fold{0..4}: done head on 5 scenario folds of train, val_scores = the held-out fold's out-of-fold scores
  (runs/ada/laya_done_cv.sbatch, jobs 49476 and 49598)
- Scored by analysis/score_step_variants.py and analysis/done_threshold_cv.py; write-up
  analysis/2026-10-31_step_nobt_and_done_cv.md
