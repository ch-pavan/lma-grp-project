# Pilot pass rates with paired differences vs S1 on the same tasks, 95% bootstrap CI over scenarios.
# usage: python laya_pilot_ci.py PILOT_DIR [PILOT_DIR2 ...]   (S1 = the first S1_record found)
import glob, json, os, sys
import numpy as np

sysrows = {}
for d in sys.argv[1:]:
    for sd in sorted(glob.glob(os.path.join(d, "*"))):
        rs = [json.loads(l) for f in glob.glob(sd + "/tasks_*.jsonl") for l in open(f)]
        name = os.path.basename(sd) + ("" if os.path.basename(sd) not in sysrows else " (" + os.path.basename(d) + ")")
        if rs:
            sysrows[name] = rs
base = sysrows["S1_record"]
rng = np.random.default_rng(0)
scen = sorted({r["scenario"] for r in base})


def per_scen(rs):
    m = {}
    for r in rs:
        m.setdefault(r["scenario"], []).append(r["passed"])
    return m


B = per_scen(base)
for name, rs in sysrows.items():
    S = per_scen(rs)
    n = len(rs); p = sum(r["passed"] for r in rs)
    errs = sum(bool(r["harness_error"]) for r in rs)
    diffs = []
    for _ in range(5000):
        pick = rng.choice(scen, len(scen))
        a = np.concatenate([S.get(s, []) for s in pick]); b = np.concatenate([B[s] for s in pick])
        diffs.append(100 * (a.mean() - b.mean()))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"{name}: {p}/{n} = {100 * p / n:.1f}%, vs S1 {100 * p / n - 100 * np.mean([r['passed'] for r in base]):+.1f} pts [{lo:+.1f}, {hi:+.1f}], "
          f"blocks/task {sum(r['interventions'] for r in rs) / n:.2f}, steps/task {sum(r['steps'] for r in rs) / n:.1f}, "
          f"forced {sum(r['error_type'] == 'harness:forced_quit' for r in rs)}, harness errors {errs}, s/task {sum(r['seconds'] for r in rs) / n:.0f}")
