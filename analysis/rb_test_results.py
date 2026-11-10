# Live test results of the 9B agent on Ada (plan item 4.7, jobs 64755, 64756, 64759, 65521, 65919): pass rate on the
# 1,200 test tasks (100 scenarios x 4 versions x 3 runs) in rollback plus done check (rbh2dc), against no judge
# (S1_record, the recorded test passes of item 4.1), with a 95% CI from a paired bootstrap over scenarios and tasks
# gained or lost, as analysis/rb_results.py does for val. Also Laya against the 9B judge, and the split by version.
# usage: python analysis/rb_test_results.py [run_dir]   (default runs/data/q9b_test, from sh runs/unpack_data.sh)
import collections, glob, json, sys

import numpy as np

D = (sys.argv[1] if len(sys.argv) > 1 else "runs/data/q9b_test").rstrip("/") + "/"


def load(p):
    return {(r["id"], r["run"]): r for f in glob.glob(p) for r in map(json.loads, open(f))}


def paired(d, base, rng):
    keys = sorted(set(d) & set(base))
    by = collections.defaultdict(list)
    for k in keys:
        by[d[k]["scenario"]].append(k)
    sc = sorted(by)
    diff = np.array([sum(d[k]["passed"] - base[k]["passed"] for k in by[s]) for s in sc], float)
    cnt = np.array([len(by[s]) for s in sc], float)
    idx = rng.integers(0, len(sc), (10000, len(sc)))
    bs = diff[idx].sum(1) / cnt[idx].sum(1) * 100
    won = sum(d[k]["passed"] and not base[k]["passed"] for k in keys)
    lost = sum(base[k]["passed"] and not d[k]["passed"] for k in keys)
    return keys, len(sc), diff.sum() / cnt.sum() * 100, np.percentile(bs, 2.5), np.percentile(bs, 97.5), won, lost


def main():
    base = load(D + "S1_record/tasks_*.jsonl")
    systems = {"no judge (64755)": base, "Laya step+done (64756)": load(D + "S_layastep@rbh2dc/tasks_*.jsonl"),
               "9B judge (64759, 65521)": load(D + "S3_llm_judge@rbh2dc/tasks_*.jsonl"),
               "oracle (64755, 65919)": load(D + "S_oracle@rbh2dc/tasks_*.jsonl")}
    rng = np.random.default_rng(0)
    print("against no judge, paired over scenarios")
    for name, d in systems.items():
        keys, ns, m, lo, hi, won, lost = paired(d, base, rng)
        f = lambda c: np.mean([d[k].get(c) or 0 for k in keys])  # noqa: E731
        err = sum(bool(d[k].get("harness_error")) for k in keys)
        print(f"{name:26s} n={len(keys)} ({ns} scenarios) pass {np.mean([d[k]['passed'] for k in keys]) * 100:5.1f}%  "
              f"{m:+5.1f} [{lo:+.1f}, {hi:+.1f}]  +{won} -{lost}  steps {f('steps'):.1f} interventions "
              f"{f('interventions'):.2f} resamples {f('resamples'):.2f} judge tokens {f('judge_in') + f('judge_out'):,.0f} "
              f"harness errors {err}")
    lay, slm = systems["Laya step+done (64756)"], systems["9B judge (64759, 65521)"]
    keys, ns, m, lo, hi, won, lost = paired(lay, slm, rng)
    print(f"\nLaya against the 9B judge: n={len(keys)} {m:+.1f} [{lo:+.1f}, {hi:+.1f}]  +{won} -{lost}")
    print("\npass rate by version")
    vers = sorted({k[0].rsplit("_", 1)[0] for k in base})
    print(f"{'':26s} " + " ".join(f"{v.replace('multi_turn_', ''):>12s}" for v in vers))
    for name, d in systems.items():
        print(f"{name:26s} " + " ".join(
            f"{np.mean([d[k]['passed'] for k in d if k[0].rsplit('_', 1)[0] == v]) * 100:11.1f}%" for v in vers))


if __name__ == "__main__":
    main()
