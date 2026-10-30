# Plain rules against Laya and the 9B judge, on the same labels (plan item 3.8, 30 Oct 2026)

**Why this exists.** The earlier rules numbers (`shuban_findings/results/offline_judges_9b_val.md`) were scored against the guide v1 LLM labels. Laya and the 9B judge in the mid report are scored against the guide v2 labels. This file scores the plain rules against the same v2 labels, on the same 1,772 validation steps of the Qwen3.5 9B agent. The positive counts match `analysis/primary_val.py`: 111 and 95 off-track steps over all steps, 45 and 44 on tool calls.

- **Annotator A** is DeepSeek V4.1 Flash, and **Annotator B** is GLM-5.3-Flash, both under guide v2.
- **Laya and the 9B judge** come from `analysis/primary_val.py`, which scores with the proposal's mapping.
- **Rules** come from Shuban's scorer, `shuban_findings/code/offline_eval.py --judge rules`.

| F1 (Annotator A / Annotator B) | Plain rules | Finetuned Laya | 9B SLM judge |
|---|---|---|---|
| Off track, all steps | 0.14 / 0.12 | 0.30 / 0.27 | 0.34 / 0.29 |
| Off track, tool calls only | 0.16 / 0.14 | 0.42 / 0.36 | 0.34 / 0.29 |
| False claim | 0.00 / 0.00 | 0.07 / 0.10 | 0.05 / 0.05 |
| Primary (mean of off track and false claim, all steps) | 0.07 / 0.06 | 0.18 / 0.19 | 0.19 / 0.17 |

**Reading:**
- **Laya against the rules.** Laya beats the plain rules on every class, by +11 to +13 primary F1 and by +16 to +26 F1 on off track.
- **Why the rules score low.** They flag 299 calls as off track, most of them wrongly: precision is 0.08 to 0.09.
- **Laya against the 9B judge.** That comparison is in the mid report's Table 13.
- **Variation.** The rules are deterministic, so they have no seed variation. Their CIs, from a bootstrap over the 15 validation scenarios, are in the per-file tables.

**Raw tables:** `analysis/rules_v2/{all,call}_annotator{A,B}.md`.

**Reproduce.** Use the unpacked validation run folder and the v2 label files from `runs/data/q9b_s1t_49146/val/`:

```
python shuban_findings/code/offline_eval.py --steps <val run dir> \
  --labels <val run dir>/annot_v2_deepseek.jsonl <val run dir>/annot_v2_glm.jsonl --judge rules --kind all --out <out>
# then --kind call for tool calls only
python analysis/primary_val.py        # Laya and the 9B judge, from inside an unpacked runs/data
```
