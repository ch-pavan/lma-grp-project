# Plan item 3.4: choose the done head's threshold from out-of-fold scores on TRAIN (runs/ada/laya_done_cv.sbatch: 5
# scenario-grouped folds, each fold's val_scores.jsonl = held-out fold), then apply it, unchanged, to the validation
# scores of the reported done head (job 49265). Validation is not used to choose anything.
# Positive class: not done (label 0 in the done data). Threshold = the one maximising F1 on the pooled out-of-fold scores.
# usage: python analysis/done_threshold_cv.py FOLDS_DIR [VAL_SCORES.jsonl] [--out FILE.md]    e.g. runs/data/laya_runs/ada_done_cv
#        default VAL_SCORES: runs/data/laya_runs/49265/val_scores.jsonl
import argparse, glob, json, os

import numpy as np


def prf(y, pred):
    y, pred = np.asarray(y, bool), np.asarray(pred, bool)
    tp = (y & pred).sum(); fp = (~y & pred).sum(); fn = (y & ~pred).sum()
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def best_threshold(y, s):
    cand = np.unique(np.concatenate([s, [0.5]]))
    f = [prf(y, s >= t)[2] for t in cand]
    i = int(np.argmax(f))
    return float(cand[i]), float(f[i])


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return np.array([1 - r["label"] for r in rows]), np.array([r["p_not_done"] for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folds_dir"); ap.add_argument("val_scores", nargs="?", default="runs/data/laya_runs/49265/val_scores.jsonl")
    ap.add_argument("--out")
    a = ap.parse_args()
    lines = ["| fold | held-out rows | not done | own best threshold | F1 there |", "|---|---|---|---|---|"]
    ys, ss = [], []
    for d in sorted(glob.glob(os.path.join(a.folds_dir, "fold*"))):
        y, s = load(os.path.join(d, "val_scores.jsonl"))
        t, f = best_threshold(y, s)
        lines.append(f"| {os.path.basename(d)} | {len(y)} | {int(y.sum())} | {t:.3f} | {f:.3f} |")
        ys.append(y); ss.append(s)
    y, s = np.concatenate(ys), np.concatenate(ss)
    thr, f_oof = best_threshold(y, s)
    yv, sv = load(a.val_scores)
    lines += ["", f"Pooled out-of-fold scores: {len(y)} train turn ends, {int(y.sum())} not done. "
                  f"Best threshold {thr:.3f} (out-of-fold F1 {f_oof:.3f}).", "",
              "| threshold on validation (495 turn ends) | how chosen | precision | recall | F1 |", "|---|---|---|---|---|"]
    for t, how in ((thr, "out-of-fold on train (this item)"), (0.5, "default, as in the live runs"),
                   (0.9835, "dev split of 8 scenarios (job 49265)")):
        p, r, f = prf(yv, sv >= t)
        lines.append(f"| {t:.3f} | {how} | {p:.3f} | {r:.3f} | {f:.3f} |")
    text = "\n".join(lines)
    print(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
