#!/usr/bin/env python3
"""Plan item 3.4: scenario-grouped folds of the done-check TRAIN split, so the done head's threshold can be chosen on
out-of-fold scores instead of the 50 dev positives (which gave threshold 0.98 and val F1 0.36) or the unjustified 0.5.

For fold k: train = the other folds, dev = val = fold k. train_laya_done.py then writes fold k's out-of-fold scores to
val_scores.jsonl. Validation (the 15 val scenarios) is never touched here. CPU only, seconds.

    python pavan_gpu/make_done_folds.py IN_DIR OUT_DIR [--k 5]
    e.g. python pavan_gpu/make_done_folds.py $H/data/laya_done $H/data/laya_done_folds
"""
import argparse
import gzip
import json
import os
import random


def read(path):
    if not os.path.exists(path) and os.path.exists(path + ".gz"):
        path += ".gz"
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir"); ap.add_argument("out_dir")
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    rows = read(os.path.join(a.in_dir, "train.jsonl"))
    scen = sorted({r["scenario"] for r in rows})
    random.Random(0).shuffle(scen)
    fold_of = {s: i % a.k for i, s in enumerate(scen)}
    for k in range(a.k):
        d = os.path.join(a.out_dir, f"fold{k}")
        os.makedirs(d, exist_ok=True)
        tr = [r for r in rows if fold_of[r["scenario"]] != k]
        ho = [r for r in rows if fold_of[r["scenario"]] == k]
        for split, rs in (("train", tr), ("dev", ho), ("val", ho)):
            with open(os.path.join(d, f"{split}.jsonl"), "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in rs)
        print(f"fold{k}: train {len(tr)} rows ({sum(1 - r['label'] for r in tr)} not done), held out {len(ho)} rows "
              f"({sum(1 - r['label'] for r in ho)} not done), {len({r['scenario'] for r in ho})} scenarios")


if __name__ == "__main__":
    main()
