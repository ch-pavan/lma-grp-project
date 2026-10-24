# Running the baselines

This harness ran every number in findings.pdf (Qwen3 8B and Qwen3.5 4B agents on RTX 2080 Ti). It runs the proposal's online baselines as they are, with one gap listed at the end.

## Setup

- Python 3.10+, `pip install vllm==0.19.1 torch==2.10.0` (cu128), plus `bfcl_eval` from a gorilla checkout (set `BFCL_LB` to `gorilla/berkeley-function-call-leaderboard`) and `agentdojo==0.1.35` for AgentDojo. Laya needs `transformers`; Granite runs as a second vLLM server.
- Unsound BFCL scenarios are dropped in run.py (gorilla issues 1367, 1267, 1137, 914). The split (100 test, 74 train, 15 val, 11 dropped) is in finetune_data/split.json.
- On a slow PyPI mirror, use `-i https://pypi.tuna.tsinghua.edu.cn/simple`.

## Serve the agent model

```
vllm serve <model> --dtype half --max-model-len 16384 --gpu-memory-utilization 0.88 --enable-prefix-caching \
  --tool-call-parser qwen3_coder --max-num-seqs 16 --limit-mm-per-prompt '{"image":0,"video":0}'
```
Qwen3 models use `--tool-call-parser hermes`. On a faster card use bf16 and drop `--dtype half`. For Granite (S4b) serve `ibm-granite/granite-guardian-3.2-3b-a800m` on port 8001.

## Run

```
python run.py --system S1_none --split test --runs 3 --out results/S1_none --model <model>
python run.py --system S2_rules ...      # plain rules
python run.py --system S3_llm_judge ...  # SLM judge, reasoning on
python run.py --system S4a_laya ...      # Laya as is (--laya-device cuda:0)
python run.py --system S4b_granite ...   # Granite on --granite-url
python agentdojo_run.py --system S1_none --runs 3 --out results_ad/S1_none --model <model>
python analyze.py results                 # pass rates, bootstrap CIs over scenarios, cost, chart (run again on results_ad)
```
`--limit N` runs N scenarios for a pilot, `--shard i/n` splits a run across servers, `--concurrency 8` matches our measured sweet spot on one 2080 Ti. Correction modes and the oracle are in actions.py (`--system S3_llm_judge@dc`, `S_oracle@rbh2dc` and so on; see its header). Every task writes one JSON row with pass, steps, blocks, tokens and seconds; step logs sit beside it.

Before a real run, replay the gold calls (`python test_gold.py`): every task must pass. If one fails, the harness is wrong, not the agent.

## Pitfalls we hit

- Qwen3.5 prints only a closing think tag. actions.py patches `strip_think` so the verdict is read after it. Give a Qwen3.5 judge `max_tokens` of at least 4096, or half its verdicts get cut mid thought.
- Long tasks overflow the context. actions.py retries the call with older tool outputs cut to 300 characters.
- Granite timed out when given every tool doc. Give it only the called tool's doc. Even then it flagged every call.
- Laya keeps the start of its input and truncates the end, so put the proposed step first in the state. Untuned, it flags almost every closing message.
- Two no judge runs on the same 120 tasks differed by 4.2 points. Treat gaps under about 5 points as noise unless there are more runs.

## Gap against the latest proposal

Q1 to Q3, the fixed rules and the state layout now match the proposal. Laya and the LLM judge both get the state with the proposed step first, then the evidence list, requests, plan and the last three calls, trimmed oldest first to 768 tokens filled by code (4 characters per token when the ModernBERT tokenizer is not cached, so the 1,024 token cap holds); `--state legacy` restores the old layout.

## Offline scorer

`offline_eval.py` runs one judge over recorded steps and scores it against labels, or compares two label sources. It needs no bfcl_eval and no Ada, so it runs on a laptop. Steps are the judge inputs of an S1_record run (`states_*.jsonl` in a run dir, or any jsonl with the same rows).

```
python offline_eval.py --steps RUN_DIR --labels RUN_DIR::oracle RUN_DIR::deepseek RUN_DIR::glm RUN_DIR::both --judge laya --device cuda:0 --out out/laya
python offline_eval.py --steps RUN_DIR --labels RUN_DIR::oracle --judge llm --base-url http://host:8000/v1 --model <name> --reasoning on --trace full --concurrency 16 --out out/llm_think_full
python offline_eval.py --agree RUN_DIR::deepseek RUN_DIR::glm --steps RUN_DIR --out out/agree
```

- Judges: `rules`, `laya` (as is), `kev`, `lettuce` (Q2 on closing messages only), `granite` (Q2 only, Ada only, it needs the 3B weights in fp32 or a vLLM server through `--granite-url`), `jev` (classifier.dev, free tier, share_data false, four requests at once), `llm` (any OpenAI compatible endpoint). The llm mode takes `--reasoning on|off`, `--trace proposal|full` and `--max-tokens`; Qwen3.5 needs at least 4096 with reasoning on. Q3 is scored for rules, laya, kev and jev only.
- Label sets, each scored on its own (a table per set, `metrics_<set>.md` and `.json`). `RUN_DIR::oracle` is labels.jsonl plus step_labels.jsonl, `::deepseek` and `::glm` are the annotator files, `::both` keeps a question only where the two annotators agree. A plain file is also accepted: annotator rows (uid, q1, q2 or a typed turn answer), `oracle_labels.py` rows, or finetune_data rows. Without `--labels` the `oracle_flag` inside the steps is used.
- Mapping to the proposal questions. A call gives Q1 (off_track under the subset rule, `--label-rule suffix` for the old one), Q2 (made_up_value from step_labels or the annotator) and Q3 (not_needed for an unneeded irreversible call). A turn end gives Q2 (false_claim) and Q1: a false claim stays on track, any other turn that is not done is off track. A question with no label on a step is not scored on that step, and a judge is scored only on the questions it can express.
- Metrics per class are precision, recall and F1 with 95% CIs from a bootstrap over scenarios (1000 draws, fixed seed). The primary number is the mean F1 of off_track (Q1) and false_claim (Q2). `--kind call|msg` scores only calls or only closing messages, `--reweight turns.jsonl` reweights steps to the real done and not done turn mix, `--limit N` takes N steps in sha256 order for a pilot.
- `--agree A B` takes two label or prediction files (or `RUN_DIR::source`) and prints agreement, Cohen's kappa and Gwet's AC1 per question with the same bootstrap. Predictions of a judge (`predictions.jsonl`) can be compared with any label set this way.
- Granite and the rule fallbacks run without the called tool's doc here, because recorded steps do not hold tool docs. The rules judge sees the calls of the current turn rebuilt from the recorded `recent` list.
- Laya on a 4 GB card: use `runjob -- python offline_eval.py ...`. Check the plumbing with `python test_offline_eval.py` (rules, label shapes, agreement, and the llm mode against a fake server).
