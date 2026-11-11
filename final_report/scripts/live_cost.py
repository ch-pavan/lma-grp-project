# Pass rate (overall with a 95% bootstrap CI over scenarios, and per BFCL version), seconds per task, judge tokens per
# task and interventions per task for the live 9B test runs on Ada (plan item 4.7). Standard library only.
# usage (repo root): python final_report/scripts/live_cost.py runs/raw/q9b_test
import glob, gzip, json, os, random, sys
from collections import defaultdict

SYSTEMS = [("No judge", "S1_record"), ("Laya (frozen)", "S_layastep@rbh2dc"), ("9B SLM judge", "S3_llm_judge@rbh2dc"),
           ("Oracle", "S_oracle@rbh2dc")]


def load(d):
    out = []
    for f in glob.glob(os.path.join(d, "tasks_*")):
        op = gzip.open if f.endswith(".gz") else open
        out += [json.loads(l) for l in op(f, "rt") if l.strip()]
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "runs/raw/q9b_test"
    for name, sub in SYSTEMS:
        r = load(os.path.join(root, sub))
        sc = defaultdict(list)
        for x in r:
            sc[x["scenario"]].append(x["passed"])
        names, rng, boot = sorted(sc), random.Random(0), []
        for _ in range(2000):
            draw = [rng.choice(names) for _ in names]
            boot.append(sum(sum(sc[s]) / len(sc[s]) for s in draw) / len(draw))
        boot.sort()
        ver = defaultdict(list)
        for x in r:
            ver[x["version"]].append(x["passed"])
        mean = lambda k: sum(x.get(k) or 0 for x in r) / len(r)
        print(f"{name}: {len(r)} tasks, pass {100 * sum(x['passed'] for x in r) / len(r):.1f}% "
              f"[{100 * boot[50]:.1f}, {100 * boot[1949]:.1f}]; "
              + ", ".join(f"{v} {100 * sum(p) / len(p):.1f}" for v, p in sorted(ver.items()))
              + f"; {mean('seconds'):.0f} s/task, judge tokens {mean('judge_in') + mean('judge_out'):.0f}/task, "
              f"interventions {mean('interventions'):.2f}/task")


if __name__ == "__main__":
    main()
