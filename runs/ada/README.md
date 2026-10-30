# Laya jobs on Ada (31 Oct 2026)

Plan items 3.7 and 3.4 (`docs/phase_plan.md`) ran on the Ada cluster under Swayam's account. The write-up is `analysis/2026-10-31_step_nobt_and_done_cv.md`, and the results are in `runs/data/laya_runs/ada_step_nobt/` and `runs/data/laya_runs/ada_done_cv/`.

| File | Plan item | What it does | Jobs |
|---|---|---|---|
| `laya_step_nobt.sbatch` | 3.7 | Step head without the oracle "breaks task" label (`nobt_seed0..2`), and with the original labels (`orig_seed0..2`) in the same setup. Job array of 6, about 45 to 55 min each. | 49477, 49597 |
| `laya_done_cv.sbatch` | 3.4 | Done head on 5 scenario-grouped folds of train; each fold's `val_scores.jsonl` holds its out-of-fold scores. Job array of 5, about 8 min each. | 49476, 49598 |
| `setup_env.sh` | | One-time setup: Python 3.12 venv made with `uv` (torch 2.7.1+cu126, laya 0.3.27), and Laya at commit `e929ae5`. | |

Which job produced each result:

| Result | Job |
|---|---|
| `ada_step_nobt/{nobt_seed1, nobt_seed2, orig_seed0, orig_seed1}` | 49477 |
| `ada_step_nobt/{nobt_seed0, orig_seed2}` | 49597 (rerun; the first attempt landed on a node whose GPU failed CUDA init) |
| `ada_done_cv/{fold0, fold2}` | 49476 |
| `ada_done_cv/{fold1, fold3, fold4}` | 49598 (rerun, same reason) |

## Settings that differ from the Turing runs

- **Precision.** Every GPU in partition `u22` is an RTX 2080 Ti (11 GB) without fast bf16. The jobs pass `--dtype fp16` to `analysis/train_laya_done.py`, which then uses a GradScaler. bf16 stays the default, so the Turing jobs are unchanged.
- **Micro-batches.** `--accum 8` (micro-batches of 4), to fit in 11 GB. The effective batch size is unchanged.
- **Like-for-like comparison.** Both step-head variants are trained in this same setup, with 3 seeds each.
- **Broken nodes.** `gnode077` and `gnode066` are excluded because their GPUs fail CUDA init.

## Steps

```
ssh <user>@ada-gw1.iiit.ac.in          # ada.iiit.ac.in no longer accepts SSH
bash setup_env.sh                       # once
# copy analysis/ and the unpacked runs/data/{laya_step,laya_done} to ~/sot/
python analysis/make_step_variant.py ~/sot/data/laya_step ~/sot/data/laya_step_nobt
python analysis/make_done_folds.py ~/sot/data/laya_done ~/sot/data/laya_done_folds --k 5
sbatch laya_step_nobt.sbatch
sbatch laya_done_cv.sbatch
```

Then score the runs on a CPU, from the repo root after `sh runs/unpack_data.sh`:

```
python analysis/score_step_variants.py runs/data/laya_runs/ada_step_nobt
python analysis/done_threshold_cv.py runs/data/laya_runs/ada_done_cv
```
