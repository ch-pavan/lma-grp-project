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

Q1 to Q3 and the fixed rules are in place: Q3 uses the irreversible tool list in run.py, an ask is counted and the scripted user always approves. The remaining gap is the state layout. Ours puts the proposed step last and does not cap it at 1,024 tokens; the proposal's Laya state needs the proposed step first and a hard 1,024 token budget (about 768 filled by code). Fix that in the state builder before the Laya runs.
