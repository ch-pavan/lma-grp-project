# Judge again, with a larger output cap, the steps of an offline_eval.py llm run that gave no verdict (reasoning ran past
# --max-tokens, or a request error). Keys (id, run, k) and the state are rebuilt from the full steps, so only those steps
# are sent. usage: python analysis/rejudge_unparsed.py STEPS_DIR PREDICTIONS.jsonl OUT.jsonl --base-url URL --model NAME
import argparse, asyncio, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shuban_findings", "code"))
import offline_eval as E  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("steps"); ap.add_argument("preds"); ap.add_argument("out")
ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True)
ap.add_argument("--max-tokens", type=int, default=8192); ap.add_argument("--concurrency", type=int, default=96)
a = ap.parse_args()
a.judge, a.reasoning, a.trace, a.state = "llm", "on", "proposal", "proposal"
redo = {(r["id"], r["run"], r["k"]) for r in map(json.loads, open(a.preds)) if not r.get("parsed")}
rows = [r for r in E.load_steps([a.steps]) if (r["id"], r["run"], r["k"]) in redo]
print(f"{len(rows)} steps to judge again, max tokens {a.max_tokens}", flush=True)
preds = asyncio.run(E.run_judge(E.JUDGES["llm"](a), rows, a, a.out))
print(f"done: {sum(bool(p.get('parsed')) for p in preds.values())} of {len(preds)} parsed", flush=True)
