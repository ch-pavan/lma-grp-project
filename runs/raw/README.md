# Raw run outputs (Qwen3.5 9B agent)

Copied from Turing `~/stay-on-task/runs/` on 25 Oct 2026, without the vLLM server logs. The `laya_test_8b/` and `q9b_test/` folders come from Ada (`~/sot/test_runs/`, `~/sot/q9b_runs/test/`), 9 Nov 2026, also without the vLLM logs. JSONL files over 500 KB are gzipped (`zcat file.jsonl.gz | head`). Results and tables built from these are in `analysis/2026-10-24_qwen35_9b_baseline.md`.

| Directory | Job(s) | What |
|---|---|---|
| `q9b_s1t_49146/` | 49146 | No judge, every step's judge input recorded (`S1_record`): val reasoning off (`val/`), val reasoning on (`val_think/`), train (`train/`), gold replay |
| `q9b_s1_49141/`, `q9b_s1_49131/` | 49141, 49131 | Earlier no judge runs and canaries |
| `q9b_dc_49274/` | 49274 | Live done check on val: no judge (`S1_none`), finetuned Laya done head (`S_layadone@dc`), 9B SLM judge (`S3_llm_judge@dc`), oracle (`S_oracle@dc`); plus the offline 9B judge on turn ends |
| `q9b_rb_49671/` | 49671, 49688, 49710, 49719, 49764 | Live rollback plus done check (`rbh2dc`) on val: Laya with the gate bug (`S_layastep@rbh2dc`), Laya fixed (`S_layastep@rbh2dc_fix`), 9B SLM judge (`S3_llm_judge@rbh2dc`, two shards), oracle (`S_oracle@rbh2dc`); offline 9B judge on val steps; GPU use CSVs |
| `q9b_slm_val/` | 50247, 50265 | 9B SLM judge offline on all 1,772 val steps (`full/`) and the rejudge of unparsed answers with 8,192 tokens (`pass2.jsonl`) |
| `laya_test_8b/` | 64349 to 64385, 64483, 64484 | Finetuned Laya (frozen heads, `runs/ada/test_freeze.md`) in the original 8B test baselines, `run.py` plain block mode: test (`test_frozen/`, two shards), the context rerun at 20,480 tokens (`test_frozen_lc20k/`), validation with done mode block, once and off (`val_block/`, `val_once/`, `val_off/`) and no judge (`val_s1/`), the pilot; job logs in `logs/` |
| `q9b_test/` | 64755, 64756 | 9B agent on test, 3 runs of 400 tasks (`runs/ada/q9b_ada.sbatch`, TP 2 on two RTX 2080 Ti): no judge with every step's judge input recorded (`S1_record`, plan item 4.1), Laya in rollback plus done check (`S_layastep@rbh2dc`, item 4.7); job log of 64756 in `logs/`. Oracle and 9B judge are added when their runs end |
| `test9b/` | rented cloud GPU (9 Nov) | 9B agent on test, no judge, every step's judge input recorded (`S1_record`): 8 passes of the 400 test tasks (3,200), vLLM 0.27.1 as on Turing (`runs/cloud/`); oracle labels, and the proposal's labelled sample (`sample_order.txt`, 7,214 steps, `analysis/sample_test.py`) |
| `test9b_labels/` | OpenCode API (9 Nov) | DeepSeek V4.1 Flash and GLM-5.3-Flash labels, guide v3: the 7,214 test steps, and in `train/` the 3,737 train closing messages (plan item 4.4) |
| `test9b_judge/` | rented cloud GPU (9 Nov) | 9B SLM judge offline on the 7,214 test steps (`runs/judge9b/full/`, 4,096 tokens) and the rejudge of its unparsed answers with 8,192 tokens (`pass2.jsonl`) |
| `typed_head/` | rented cloud GPU (9 Nov) | Plan item 4.4, the typed closing-message head (`analysis/2026-11-09_typed_closing_head.md`): out-of-fold and seed runs (`out/`), thresholds and choice (`select/`), Laya's scores on the test steps (`laya_test_scores.jsonl`), the final test table (`primary_test.md`). Weights on release `laya-typed-head-2026-11-09` |

The `test9b*` and `typed_head` folders keep JSONL gzipped only (`gunzip -k` restores it before running the scripts).

In each system directory, `steps_*.jsonl` holds one row per step (judge input, verdict, action) and `states_*.jsonl` the environment state after each step.
