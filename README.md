# Stay on Task: can a small classifier correct local agents' drift?

LMA Group Project 2026: Shuban Biswas, Ch Pavan Harshit, Swayam Goyal, Aaditya Sharma.

We test whether **Laya**, a 0.4B typed-decision classifier finetuned for the job, can replace a reasoning **Qwen3.5 9B
SLM judge** as the step checker of a small local agent on **BFCL v4 multi turn**.

| Result (test set) | Laya | 9B SLM judge |
|---|---|---|
| Pass rate, 1,200 tasks, rollback plus done check (no judge 45.5%) | **49.2%** (+3.7 [+0.8, +6.8]) | 49.2% (+3.7 [+1.1, +6.5]) |
| Judge tokens per task | **0** | 52,672 |
| Seconds per task | **528** | 1,621 |
| Primary F1 on 7,214 labelled steps (typed closing-message head) | **0.38 to 0.44** | 0.24 to 0.25 |

Final report: `final_report/Stay_On_Task_final_report.pdf`. Mid report: `mid_submission/condensed/Stay_On_Task_mid_report.pdf`.
Proposal: `proposal/Stay_On_Task_proposal.pdf`.

## Repository layout

| Folder | What |
|---|---|
| `shuban_findings/code/` | Agent harness (planner, doer, judges, rollback, done check), replay oracle, plain rules, offline scorer `offline_eval.py`. Setup and pitfalls: `shuban_findings/code/RUNNING.md` |
| `analysis/` | Oracle and step labels, LLM annotation (`annotate.py`), Laya data builders, training (`train_laya_done.py`, `train_laya_typed.py`), scoring and result scripts, dated write-ups |
| `human_check/` | Labelling guides (v2, v3), check samples, both checkers' sheets, referee decisions, `score.py` |
| `runs/raw/` | Every run's raw outputs (tasks, steps, judge inputs), annotator labels, logs. Index: `runs/raw/README.md` |
| `runs/data/` | Labels, Laya datasets, Laya validation scores. Rebuild with `sh runs/unpack_data.sh` |
| `runs/turing/`, `runs/ada/`, `runs/cloud/` | GPU job scripts for the three machines we used, each with a README |
| `docs/phase_plan.md` | Plan with owners and status of every item |
| `final_report/` | Final report source, figures (`make_figs.py`), number-to-source map (`sources.md`), helper scripts |

## Setup

1. Python 3.10+ with `numpy`. The harness needs `vllm`, `bfcl_eval` from a gorilla checkout at commit `6ea5797`
   (set `BFCL_LB` to `gorilla/berkeley-function-call-leaderboard`) and `agentdojo==0.1.35`. Exact pins: `shuban_findings/code/RUNNING.md`.
2. Laya: `pip install laya==0.3.27`, model `convaiinnovations/laya-typed-decisions` at revision `e929ae5`
   (`runs/ada/setup_env.sh` does both). Finetuned weights: GitHub releases `laya-heads-frozen-2026-11-08` (step and
   done heads, split into parts with `parts.sha256`) and `laya-typed-head-2026-11-09`.
3. Agent model: `cyankiwi/Qwen3.5-9B-AWQ-4bit` (revision `e4d2d39c`) served by vLLM with `--tool-call-parser qwen3_coder`,
   reasoning off. Server settings per machine: `runs/cloud/serve.sh`, `runs/ada/q9b_ada.sbatch`.
4. Unpack the tracked data: `sh runs/unpack_data.sh`. The `test9b*`, `typed_head` and `typed_live` folders keep JSONL
   gzipped; `gunzip -k` them before running the scripts that read them.

## Reproduce the results (CPU only, from the tracked data)

| Report item | Command |
|---|---|
| Live test results (Table 6, Figure 7) | `python analysis/rb_test_results.py` |
| Live cost and per version results | `python final_report/scripts/live_cost.py runs/raw/q9b_test` |
| Typed head live run | `python analysis/live_compare.py` |
| Primary metric on test (Table 7, Figure 8) | `python analysis/primary_test.py` (output: `runs/raw/typed_head/primary_test.md`) |
| Annotator agreement on test | `python final_report/scripts/test_agreement.py runs/raw/test9b_labels` |
| Failure types on test (Figure 9) | `python analysis/oracle_labels.py RUN_DIR` on the unpacked `runs/raw/test9b/test` |
| Primary metric on validation | `python analysis/primary_val.py` |
| Step head seeds and done threshold (Phase 3) | `python analysis/score_step_variants.py runs/data/laya_runs/ada_step_nobt`; `python analysis/done_threshold_cv.py runs/data/laya_runs/ada_done_cv` |
| Annotation check against humans | `python human_check/score.py human_check/val2 --guide v3` |
| Report figures | `python final_report/make_figs.py` (needs matplotlib), then `sh final_report/compile.sh` |

## Rerun on a GPU

- **Agent runs and the live checks:** `runs/cloud/README.md` (one rented GPU: 8 no-judge test passes, oracle labels,
  test sample, 9B judge, typed head training and live run) and `runs/ada/README.md` (Ada cluster jobs).
- **Laya training:** `python analysis/train_laya_done.py DATA MODEL OUT --question step|done --mode full` for the step and done heads;
  `analysis/build_typed_data.py`, `analysis/train_laya_typed.py` and `analysis/typed_select.py` for the typed head
  (driven by `runs/cloud/typed_auto.sh`). A full finetune takes minutes on one 24 to 48 GB GPU.
- **LLM annotation:** `OPENCODE_KEY=... python analysis/annotate.py RUN_DIR MODEL OUT.jsonl --guide v3` with
  `deepseek-v4.1-flash` and `glm-5.3-flash`.

Every threshold and stop rule was fixed on train or dev before test data was used; the freeze notes are
`runs/ada/test_freeze.md` and `analysis/2026-11-09_typed_closing_head.md`.
