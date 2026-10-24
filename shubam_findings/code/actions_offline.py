# The S3 judge prompt over recorded step states (laya_run.py S1_record), for comparing judge models on identical steps.
# Steps are taken in sha256 order of (id, run, k), so every judge model sees the same subset.
# usage: python actions_offline.py STATES.jsonl OUT.jsonl BASE_URL MODEL [LIMIT] [CONCURRENCY]
import asyncio, hashlib, json, sys, time
from collections import defaultdict
import actions as A
import prompts as P
import run as R

states_p, out_p, url, model = sys.argv[1:5]
limit = int(sys.argv[5]) if len(sys.argv) > 5 else 600
conc = int(sys.argv[6]) if len(sys.argv) > 6 else 12
recs, seen = [], defaultdict(int)
for l in open(states_p):
    r = json.loads(l)
    key = (r["id"], r["run"])
    r["k"] = seen[key]; seen[key] += 1
    recs.append(r)
recs.sort(key=lambda r: hashlib.sha256(f"{r['id']}|{r['run']}|{r['k']}".encode()).hexdigest())
recs = recs[:limit]
llm = A.LPLLM(url, model)
judge = R.LLMJudge(llm)
sem = asyncio.Semaphore(conc)
f = open(out_p, "w")


async def one(r):
    async with sem:
        t = time.time()
        step = dict(r["step"])
        step["ev"] = [tuple(x) for x in step.get("ev", [])]
        ctx = {"requests": r["requests"], "plan": r["plan"], "recent": [tuple(x) for x in r["recent"]], "turn_calls": [], "tools": []}
        A.LP.set(None)
        v = await judge.judge(ctx, step)
        f.write(json.dumps({"id": r["id"], "run": r["run"], "k": r["k"], "kind": step["kind"], "q1": v["q1"], "q2": v["q2"],
                            "flag": int(v["q1"] == "off_track" or v["q2"] != "none"), "p_flag": A.p_flag(v, A.LP.get()),
                            "parsed": v.get("parsed"), "jout": v["jout"], "s": time.time() - t}) + "\n")
        f.flush()


async def main():
    t = time.time()
    await asyncio.gather(*(one(r) for r in recs))
    print(f"judged {len(recs)} steps with {model} in {time.time()-t:.0f}s", flush=True)

asyncio.run(main())
