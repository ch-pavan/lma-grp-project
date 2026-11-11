# Test run on a rented cloud GPU (plan items 4.1, 4.2 and the 9B judge for 4.5)

Turing is not available, so the 9B work runs on one rented 80 GB cloud GPU (a spot instance on a teammate's account,
paid from its grant credits). Written 9 Nov 2026, **before any test step exists**: everything under "Fixed
before looking" is decided now and is not changed after test data is seen.

## Fixed before looking

| Choice | Value | Why |
|---|---|---|
| Agent | Qwen3.5 9B, `cyankiwi/Qwen3.5-9B-AWQ-4bit` at revision `e4d2d39c` (unchanged since 19 Oct, before the val runs), vLLM 0.27.1, 32k context, reasoning off | Same as the val runs (job 49146) |
| Tasks | BFCL multi turn **test** split (100 scenarios) x 4 versions x **8 passes** = 3,200 tasks, `S1_record` (no judge, every step's judge input saved) | Stop rule of `docs/phase_plan.md` 4.1 and the mid report: until 300 false claims or 8 passes. From the val rate, 8 passes give well under 300 false claims, so 8 passes is the stop |
| Oracle labels | `analysis/oracle_labels.py`, unchanged (reproduces the val `labels.jsonl` and `turns.jsonl` byte for byte) | |
| Sample | `analysis/sample_test.py`, seed 0: failed turns in random order, each up to and including its first oracle off track call; then whole passed turns up to 500 steps | The proposal's "Test labels" rule |
| Stop rule for the sample | Walk the failed turns in order; stop at the end of the turn where off track and false claim each reach 300 positives on which both annotators agree, or when the failed turns run out | Proposal: "until off track and false claim each reach 300 positives". The val rate predicts the failed turns run out first (about 9,000 failed turn steps, about 50 agreed false claims), so the sample is expected to be every failed turn step plus 500 passed turn steps, about 9,500 steps |
| Test labels | DeepSeek V4.1 Flash and GLM-5.3-Flash through `analysis/annotate.py`, **guide v3**, every step of the sample | `docs/phase_plan.md` 4.2 |
| 9B SLM judge | `offline_eval.py --judge llm --reasoning on` (harness prompt, proposal state, 4,096 tokens), then `rejudge_unparsed.py` with 8,192 tokens on steps without a verdict | Exactly as on val (jobs 50247 and 50265) |
| Laya | **To be fixed by the team before scoring**: which step head (3 Ada seeds, `docs/phase_plan.md` 3.7) and done head, and their thresholds (done head 0.561 from 3.4) | Laya only meets test data at scoring (4.5) |

Changes to code for this run, both off by default so earlier results are unchanged: `offline_eval.py --keys FILE`
(judge only the listed steps, in that order) and `--resume` (keep rows already judged), and `rejudge_unparsed.py
--resume`. Tested on the val steps with the rules judge: 50 listed keys judged, cut to 20, resumed to 50 with no duplicates.

## Steps

All `jl` commands run on the Mac (CLI in a venv; API key in `JL_API_KEY`).

| # | Where | Command | Time, cost (estimates) |
|---|---|---|---|
| 0 | Mac | `bash runs/cloud/make_bundle.sh /tmp/bundle.tgz`; `jl ssh-key add ~/.ssh/id_ed25519.pub --name pavan-mac` | free |
| 1 | Mac | `jl create --gpu GPU_NAME --spot --storage 100 --name sot-test` (check the exact GPU name with `jl gpus`), `jl upload ID /tmp/bundle.tgz sot/bundle.tgz` | a minute |
| 2 | instance | `bash ~/sot/runs/cloud/setup.sh` then `bash ~/sot/runs/cloud/serve.sh` | ~15 min |
| 3 | instance | `bash ~/sot/runs/cloud/passes.sh canary` (3 tasks). **Stop and check**: it runs, vLLM sees the GPU, seconds per task | ~5 min. Steps 1 to 3 about ₹30 |
| 4 | instance | `nohup bash ~/sot/runs/cloud/passes.sh run > ~/sot/passes.log 2>&1 &` and `bash ~/sot/runs/cloud/watch.sh`; on the Mac `bash runs/cloud/sync.sh ID` | ~1.5 to 2 h, ~₹130 to 170 |
| 5 | instance | `cd ~/sot && venv/bin/python analysis/oracle_labels.py runs/test && venv/bin/python analysis/sample_test.py runs/test sample` | ~3 min |
| 6 | instance | `nohup bash ~/sot/runs/cloud/judge.sh ~/sot/sample_order.txt > ~/sot/judge.log 2>&1 &` | ~2 h for ~9,500 steps, ~₹170 |
| 6b | Mac, during 6 | `OPENCODE_KEY=$(cat ~/.config/stay-on-task/opencode_key) python analysis/annotate.py runs/raw/test9b_sync/runs/test MODEL runs/raw/test9b_sync/runs/test/annot_v3_NAME.jsonl --guide v3 --uids runs/raw/test9b_sync/sample_order.txt --conc 32` with MODEL `deepseek-v4.1-flash` and `glm-5.3-flash` (the models and guide of the v3 val check), both at once | ~25 to 100 min (val ran 95 to 440 steps a minute), ~$6 |
| 7 | Mac | Last sync, check the files, then `jl destroy ID` | stops all charges |

GPU total about 4.5 to 5 hours, about ₹400 of the ₹4,628 grant.

**Using the whole GPU.** Turing ran 56 tasks at once on 48 GB. The 80 GB GPU starts at `CONC=128` with vLLM
`--max-num-seqs 256` and 92% of memory. `watch.sh` prints running and waiting requests and KV cache use each minute:
raise `CONC` while nothing waits and the cache stays under about 80%, lower it if requests wait or get preempted.
Changing it means restarting `passes.sh`, which resumes, so only the tasks in flight are redone.

**Spot interruptions.** Restart with `serve.sh` then the same `passes.sh run` or `judge.sh`. `passes.sh` runs
`clean_partial.py` first: the recorder writes steps as they happen, so an episode cut mid-way would otherwise leave
partial rows and shift every step index when it reruns. If the instance does not come back, create a new one, run
setup, upload `runs/raw/test9b_sync/runs/test` back to `~/sot/runs/test`, and resume.

## Results

The synced outputs land in `runs/raw/test9b_sync/` (gzip the large JSONL files before committing, as in `runs/raw/`).
