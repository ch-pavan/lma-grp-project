# Offline sweep: laya P(flag) for every state format x question on recorded judge inputs.
# usage: python laya_sweep.py OUT.jsonl STATES.jsonl [STATES2.jsonl ...]   (env: LIMIT_GOLD, MAX_LEN, PAIRS=all|smoke)
import json, os, sys, time
import torch
import laya
import laya_variants as LV

out, srcs = sys.argv[1], sys.argv[2:]
FMTS = ["orig", "step_first", "compact", "dict"]
QIDS = ["q1_orig", "q2_orig", "q_proceed", "q_3way", "q_wrong", "q_ok", "q2_noul"]
PAIRS = [(f, q) for f in FMTS for q in QIDS] + [("step_first", "q1_swap")]
if os.environ.get("PAIRS") == "cut":  # iter1b: orig kept only as the as is reference
    PAIRS = [("orig", "q1_orig"), ("orig", "q2_orig")] + [("step_first", q) for q in QIDS + ["q1_swap"]] + \
            [(f, q) for f in ("compact", "dict") for q in ("q_proceed", "q_wrong", "q_ok", "q2_noul")]
if os.environ.get("PAIRS") == "smoke":
    PAIRS = [("orig", "q2_orig"), ("step_first", "q_wrong")]

recs = []
for p in srcs:
    rows = [json.loads(l) for l in open(p)]
    src = os.path.basename(p)
    seen = {}
    for r in rows:  # index within its episode, the key the oracle labels use
        r["k"] = seen.get((r["id"], r["run"]), 0); seen[(r["id"], r["run"])] = r["k"] + 1
    lim = int(os.environ.get("LIMIT_GOLD", "0"))
    if "gold" in src and lim:
        rows = rows[::max(1, len(rows) // lim)][:lim]  # even spread over scenarios and versions
    for r in rows:
        r["src"] = src
    recs += rows
done = set()
if os.path.exists(out):  # resume: skip states already written
    done = {(d["src"], d["id"], d["run"], d.get("k")) for d in map(json.loads, open(out))}
recs = [r for r in recs if (r["src"], r["id"], r["run"], r["k"]) not in done]
print(len(recs), "states to do,", len(done), "already done,", len(PAIRS), "pairs", flush=True)

if torch.cuda.is_available():
    torch.cuda.set_per_process_memory_fraction(float(os.environ.get("VRAM_FRAC", "0.5")))
agent = laya.load("convaiinnovations/laya-typed-decisions", device="cuda:0" if torch.cuda.is_available() else "cpu")
t0 = time.time()
CH = 128
with open(out, "a") as f:
    for s in range(0, len(recs), CH):
        part = recs[s:s + CH]
        feats = LV.features(agent, part, PAIRS, batch_size=int(os.environ.get("BS", "16")),
                            max_len=int(os.environ["MAX_LEN"]) if os.environ.get("MAX_LEN") else None)
        for r, ft in zip(part, feats):
            keep = {k: r[k] for k in ("src", "id", "run", "k", "version", "scenario", "turn", "gold_turn", "n_recent")}
            keep["step"] = {k: r["step"].get(k) for k in ("kind", "name", "args", "text")}
            f.write(json.dumps({**keep, "f": ft}, default=str) + "\n")
        f.flush()
        print(f"{s + len(part)}/{len(recs)} {time.time() - t0:.0f}s", flush=True)
print("SWEEP DONE", f"{time.time() - t0:.0f}s")
