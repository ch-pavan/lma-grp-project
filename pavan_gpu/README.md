# GPU work for Pavan (Turing)

Hi Pavan! This folder has everything for the GPU items in `docs/phase_plan.md`.
- **What to do:** run the jobs below on Turing, and put their outputs in `pavan_gpu/results/`. The job scripts do that for you.
- **What to send back:** commit and push only `pavan_gpu/results/`.
- **What we do next:** we score everything on our side, merge it into the repo, and delete this folder.

Every script uses your setup from the earlier jobs: the same account and node, the vLLM 0.27.1 container, `$H=/home/pavan.harshit/stay-on-task` and `$S=/scratch/pavan.harshit`.

## 0. Setup (once, about 2 minutes)

```
cd $H && git pull                                   # or copy pavan_gpu/ into $H if $H is not the repo checkout
ls $H/data/laya_step $H/data/laya_done              # the step and done data from jobs 49656 and 49265
ls $S/models/laya-typed-decisions $S/pylaya         # Laya weights and package from prep_laya.sbatch
mkdir -p $H/logs
```

**If `$H/data/laya_step` or `$H/data/laya_done` is missing,** rebuild them from the repo: `sh runs/unpack_data.sh` gives `runs/data/laya_step/` and `runs/data/laya_done/`. Then copy them to `$H/data/`.

## The jobs, in order

| Job | Plan item | What it does | GPU time | When |
|---|---|---|---|---|
| `jobs/a_step_nobt.sbatch` | 3.7 | Retrains the step head without the oracle "breaks_task" label (3 seeds), plus seeds 1 and 2 of the current setup | about 1.5 h | now |
| `jobs/b_done_cv.sbatch` | 3.4 | Done head on 5 scenario folds of train, to choose its threshold without touching validation | about 20 min | now |
| `jobs/c_test_passes.sbatch` | 4.1 | 9B agent, no judge, recorded on the 100 test scenarios × 4 versions, 4 passes | about 1.5 to 2 h | from 1 Nov |

```
sbatch $H/pavan_gpu/jobs/a_step_nobt.sbatch
sbatch $H/pavan_gpu/jobs/b_done_cv.sbatch
# from 1 Nov:
sbatch --export=ALL,PASSES=4 $H/pavan_gpu/jobs/c_test_passes.sbatch
```

Jobs a and b can run at the same time.

**Each job starts with a canary.** If it prints `CANARY_FAILED` or `FOLD k FAILED`, send us the log lines it shows. Each job ends by printing `ALL_DONE`.

### Why each job, in one line

- **a:** the step head trains mostly on the oracle off-track rule, which failed the proposal's 80% agreement rule. Without it, there are 209 bad training calls instead of 408. This shows how much Laya depends on that rule.
- **b:** the done head's F1 is 0.53 at threshold 0.5, but 0.36 at the threshold chosen on 50 dev positives. Out-of-fold scores on train give a threshold we can defend.
- **c:** the primary metric must be measured on test, and test needs enough false claims. The stop rule is fixed now: keep adding passes until the two LLM annotators agree on 300 false claims, or 8 passes. We count after annotating each batch. If 4 passes are not enough, we will ask you for `PASSES=4` once more.

## Running on Ada instead (Swayam's account, 31 Oct)

Pavan was unavailable, so jobs a and b run on Ada under Swayam's account. Two settings differ from Turing:
- **Precision.** All Ada GPUs in partition `u22` are RTX 2080 Ti (11 GB), which have no fast bf16. The Ada jobs pass `--dtype fp16` to `analysis/train_laya_done.py`; the option was added with a GradScaler, and bf16 stays the default, so Turing runs are unchanged.
- **Micro-batches.** They use `--accum 8` (micro-batches of 4) to fit in 11 GB.

To keep the comparison like-for-like, job a trains both variants on Ada, with 3 seeds each: `nobt_seed0..2` and `orig_seed0..2`.

| File | What |
|---|---|
| `jobs/ada_a_step_nobt.sbatch` | Item 3.7: job array of 6 runs, about 1 to 1.2 h each on a 2080 Ti |
| `jobs/ada_b_done_cv.sbatch` | Item 3.4: job array of 5 folds, about 15 min each |

**Setup on Ada:**
- **Gateway.** `ada.iiit.ac.in` no longer accepts SSH; use `ada-gw1` or `ada-gw2`.
- **Python environment.** `~/sot/venv`, built with `uv` (Python 3.12, torch 2.7.1+cu126, laya 0.3.27).
- **Model.** Laya at the pinned commit, in `~/sot/models/laya-typed-decisions`.
- **Data.** `~/sot/data`, unpacked from `runs/data`. The prep scripts are run once before submitting.

**Canary (job 49469).** fp16 runs, with peak memory 9.8 GB, at 17 s per epoch on 200 rows.

Results go to `results/a_step_nobt_ada/` and `results/b_done_cv_ada/`.

## After the jobs

```
python $H/pavan_gpu/check_results.py              # after a and b
python $H/pavan_gpu/check_results.py --with-c     # after c
cd <repo> && git pull
git add pavan_gpu/results && git commit -m "Pavan GPU results: <jobs>" && git push
```

If `$H` isn't the repo, copy `$H/pavan_gpu/results/` into the repo's `pavan_gpu/results/` first.

**Please don't change** `make_step_variant.py`, `make_done_folds.py` or the job settings. If something has to change to run, note what and why in `results/NOTES.md`.

## What lands in `results/`

| Folder | Files | Size |
|---|---|---|
| `a_step_nobt/` | `variant.txt`, plus `{nobt_seed0,1,2, orig_seed1,2}/results.json, val_scores.jsonl, <run>.log`, and `gpu.csv` | about 1 MB |
| `b_done_cv/` | `folds.txt`, plus `fold0..4/results.json, val_scores.jsonl, fold<k>.log` | about 0.5 MB |
| `c_test_passes/` | `test/*.jsonl.gz` (tasks, steps, states), `test_summary.txt`, `test.log` | about 10 to 30 MB |

Model weights (`weights.pt`) stay on Turing; they are not needed in git.

## What we do with them (our side, CPU)

1. **Job a:** score the step head with and without "breaks_task" against the LLM annotations and the replay labels, with 3 seeds.
2. **Job b:** pick the done-head threshold from the pooled out-of-fold scores, and apply it to the existing 49265 validation scores.
3. **Job c:** oracle labels (`analysis/oracle_labels.py`), then LLM annotation of the test steps with guide v3 (`analysis/annotate.py`), then the 100-step human check.
4. **Then:** update the report, move these results into `runs/` and `analysis/`, and delete `pavan_gpu/`.
