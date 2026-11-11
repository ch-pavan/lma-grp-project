# Live run of the item 4.4 typed head (analysis/2026-11-09_typed_closing_head.md, "Live run") against the 8 no-judge
# test passes: task pass rate, and the difference with a 95% bootstrap CI over the 100 test scenarios (a scenario's
# number is shared by its 4 versions; each scenario's pass rate is taken over its versions and runs).
# usage: python analysis/live_compare.py BASE_TASKS.jsonl[.gz] LIVE_TASKS.jsonl[.gz]...
import collections, gzip, json, sys

import numpy as np


def rows(p):
    with (gzip.open(p, "rt") if p.endswith(".gz") else open(p)) as f:
        return [json.loads(l) for l in f if l.strip()]


def by_scen(rs):
    d = collections.defaultdict(list)
    for r in rs:
        d[r["id"].rsplit("_", 1)[1]].append(bool(r["passed"]))
    return d


def main():
    base = rows(sys.argv[1]); live = [r for p in sys.argv[2:] for r in rows(p)]
    err = sum(bool(r.get("harness_error")) for r in live)
    B, L = by_scen(base), by_scen(live)
    names = sorted(set(B) & set(L))
    b = np.array([np.mean(B[n]) for n in names]); l = np.array([np.mean(L[n]) for n in names])
    w_b = np.array([len(B[n]) for n in names]); w_l = np.array([len(L[n]) for n in names])
    rng = np.random.default_rng(0); idx = rng.integers(0, len(names), (10000, len(names)))
    # pooled pass rate per resample (weights keep a scenario's share as in the full data)
    pb = (b[idx] * w_b[idx]).sum(1) / w_b[idx].sum(1); pl = (l[idx] * w_l[idx]).sum(1) / w_l[idx].sum(1)
    d = (pl - pb) * 100
    rb, rl = np.mean([x for n in names for x in B[n]]), np.mean([x for n in names for x in L[n]])
    iv = np.mean([r.get("interventions", 0) for r in live])
    print(f"no judge: {len(base)} tasks, pass {rb * 100:.1f}%")
    print(f"Laya typed live: {len(live)} tasks ({err} harness errors), pass {rl * 100:.1f}%, interventions per task {iv:.2f}")
    print(f"difference {(rl - rb) * 100:+.1f} points [95% CI {np.percentile(d, 2.5):+.1f}, {np.percentile(d, 97.5):+.1f}] "
          f"over {len(names)} scenarios")


if __name__ == "__main__":
    main()
