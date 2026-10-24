# Oracle labels for recorded live steps (the proposal's Q1 auto label rule plus the false claim rule), CPU only.
# usage: python laya_labels.py STATES.jsonl STEPS.jsonl OUT.jsonl
import json, sys
from collections import defaultdict
import run as R
import oracle

states_p, steps_p, out_p = sys.argv[1:4]
E = {e["id"]: e for v in R.VERSIONS for e in R.load_version(v)}
dec = {}
for l in open(steps_p):
    r = json.loads(l)
    dec[(r["id"], r["run"])] = r["decoded"]
recs = defaultdict(list)
for l in open(states_p):
    r = json.loads(l)
    recs[(r["id"], r["run"])].append(r)
j = oracle.OracleJudge()
n = flagged = 0
with open(out_p, "w") as f:
    for (tid, run), rs in recs.items():
        d = dec.get((tid, run))
        if d is None:
            continue
        executed = [c for turn in d for st in turn for c in st]
        per_turn = [sum(len(st) for st in turn) for turn in d]
        for k, r in enumerate(rs):
            t = r["turn"]
            if t >= len(d):
                continue
            y = oracle.offline_label(j, E[tid], executed, r["n_recent"], sum(per_turn[:t]), t, r["step"])
            f.write(json.dumps({"id": tid, "run": run, "k": k, "kind": r["step"]["kind"], "oracle": y}) + "\n")
            n += 1; flagged += y
print(f"labelled {n} steps, oracle flags {flagged}")
