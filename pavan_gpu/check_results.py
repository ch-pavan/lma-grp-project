#!/usr/bin/env python3
"""Check that pavan_gpu/results/ has everything the team needs before you push. Prints OK or what is missing.

    python pavan_gpu/check_results.py            # checks jobs a and b
    python pavan_gpu/check_results.py --with-c   # also checks the test passes (job c, from 1 Nov)
"""
import glob
import json
import os
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
EXPECT = {
    "a_step_nobt": [f"{run}/{f}" for run in ("nobt_seed0", "nobt_seed1", "nobt_seed2", "orig_seed1", "orig_seed2")
                    for f in ("results.json", "val_scores.jsonl")] + ["variant.txt"],
    "b_done_cv": [f"fold{k}/{f}" for k in range(5) for f in ("results.json", "val_scores.jsonl")] + ["folds.txt"],
}


def main():
    jobs = dict(EXPECT)
    if "--with-c" in sys.argv:
        jobs["c_test_passes"] = ["test_summary.txt", "test.log"]
    bad = 0
    for job, files in jobs.items():
        miss = [f for f in files if not os.path.exists(os.path.join(R, job, f))]
        rows = ""
        if job == "a_step_nobt" and not miss:
            n = {len(open(os.path.join(R, job, r, "val_scores.jsonl")).readlines()) for r in ("nobt_seed0", "orig_seed1")}
            rows = f", val rows {sorted(n)} (expect 2427)"
        if job == "c_test_passes" and not miss:
            gz = glob.glob(os.path.join(R, job, "test", "*.jsonl.gz"))
            miss += [] if any("tasks_" in g for g in gz) and any("states_" in g for g in gz) else ["test/tasks_*.jsonl.gz and states_*.jsonl.gz"]
        print(f"{job}: {'OK' if not miss else 'MISSING ' + ', '.join(miss)}{rows}")
        bad += bool(miss)
    for f in glob.glob(os.path.join(R, "*", "*", "results.json")):
        try:
            json.load(open(f))
        except Exception as e:
            print(f"unreadable {f}: {e}"); bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
