# Test sample for the primary metric, as the proposal's "Test labels" paragraph says: failed turns picked at random, every
# labelled step up to and including the first off track call (oracle, subset rule), plus whole passed turns up to 500 steps.
# Labelled steps are calls and turn end closing messages, the units annotate.py and offline_eval.py score.
# The order is fixed here, before any test label exists (seed 0). Labelling and the 9B judge walk it from the top;
# the stop rule is applied on the LLM labels: stop at the end of the turn where off track and false claim each reach
# 300 positives on which both annotators agree, or when the failed turns run out. Passed turns are always all included.
# usage: python analysis/sample_test.py RUN_DIR OUT_PREFIX      (RUN_DIR holds labels.jsonl and turns.jsonl from oracle_labels.py)
# writes OUT_PREFIX_order.txt (uid per line: id|run|k|call or id|run|k|turn, failed turns first in their random order,
# then the passed turn steps) and OUT_PREFIX_meta.json (counts and the rule)
import json, random, sys
from collections import defaultdict

SEED, PASSED_CAP, TARGET = 0, 500, 300


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def uid(r):
    return f"{r['id']}|{r['run']}|{r['k']}|{'call' if r['kind'] == 'call' else 'turn'}"


def main():
    d, out = sys.argv[1], sys.argv[2]
    done = {(t["id"], t["run"], t["turn"]): t["done"] for t in jl(f"{d}/turns.jsonl")}
    by = defaultdict(list)
    for r in jl(f"{d}/labels.jsonl"):
        if r["kind"] == "call" or r.get("turn_end"):
            by[(r["id"], r["run"], r["turn"])].append(r)
    failed, passed = [], []
    for key in sorted(by, key=lambda x: (x[0], x[1], x[2])):
        steps = sorted(by[key], key=lambda r: r["k"])
        if done.get(key) == 0:
            cut = []
            for r in steps:
                cut.append(r)
                if r["kind"] == "call" and r.get("off_track_subset"):
                    break
            failed.append((key, cut))
        elif done.get(key) == 1:
            passed.append((key, steps))
    rng = random.Random(SEED)
    rng.shuffle(failed)
    rng.shuffle(passed)
    keep, n = [], 0
    for key, steps in passed:
        if n + len(steps) > PASSED_CAP:
            continue
        keep.append((key, steps)); n += len(steps)
    lines = [uid(r) for _, s in failed for r in s] + [uid(r) for _, s in keep for r in s]
    open(f"{out}_order.txt", "w").write("\n".join(lines) + "\n")
    meta = {"run_dir": d, "seed": SEED, "passed_cap": PASSED_CAP, "target_positives": TARGET,
            "failed_turns": len(failed), "failed_turn_steps": sum(len(s) for _, s in failed),
            "passed_turns_kept": len(keep), "passed_turn_steps": n,
            "oracle_off_track_in_failed": sum(r.get("off_track_subset", 0) for _, s in failed for r in s),
            "oracle_false_claim_in_failed": sum(r.get("false_claim", 0) for _, s in failed for r in s),
            "rule": "failed turns in this order (steps up to the first oracle off track call), then the passed turn steps; "
                    "labelling stops at the end of the failed turn where off track and false claim each reach 300 agreed "
                    "positives, or when the failed turns run out"}
    json.dump(meta, open(f"{out}_meta.json", "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
