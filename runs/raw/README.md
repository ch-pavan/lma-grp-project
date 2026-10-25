# Raw run outputs (Qwen3.5 9B agent)

Copied from Turing `~/stay-on-task/runs/` on 25 Oct 2026, without the vLLM server logs. JSONL files over 500 KB are gzipped (`zcat file.jsonl.gz | head`). Results and tables built from these are in `analysis/2026-10-24_qwen35_9b_baseline.md`.

| Directory | Job(s) | What |
|---|---|---|
| `q9b_s1t_49146/` | 49146 | No judge, every step's judge input recorded (`S1_record`): val reasoning off (`val/`), val reasoning on (`val_think/`), train (`train/`), gold replay |
| `q9b_s1_49141/`, `q9b_s1_49131/` | 49141, 49131 | Earlier no judge runs and canaries |
| `q9b_dc_49274/` | 49274 | Live done check on val: no judge (`S1_none`), finetuned Laya done head (`S_layadone@dc`), 9B SLM judge (`S3_llm_judge@dc`), oracle (`S_oracle@dc`); plus the offline 9B judge on turn ends |
| `q9b_rb_49671/` | 49671, 49688, 49710, 49719, 49764 | Live rollback plus done check (`rbh2dc`) on val: Laya with the gate bug (`S_layastep@rbh2dc`), Laya fixed (`S_layastep@rbh2dc_fix`), 9B SLM judge (`S3_llm_judge@rbh2dc`, two shards), oracle (`S_oracle@rbh2dc`); offline 9B judge on val steps; GPU use CSVs |
| `q9b_slm_val/` | 50247, 50265 | 9B SLM judge offline on all 1,772 val steps (`full/`) and the rejudge of unparsed answers with 8,192 tokens (`pass2.jsonl`) |

In each system directory, `steps_*.jsonl` holds one row per step (judge input, verdict, action) and `states_*.jsonl` the environment state after each step.
