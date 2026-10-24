# Shared scoring for every offline step judge (laya variants, Jev, the feature trees classifier).
# Labels: gold replay steps are good (0); a live step's label is the oracle verdict (oracle.py offline_label).
# Threshold: best F1 on train live steps while train gold false flags stay at or under MAX_GOLD.
import json
from collections import defaultdict
import numpy as np
import run as R

MAX_GOLD = 0.05
SP = R.split()
SPLIT_OF = {s: k for k in ("train", "val", "test") for s in SP[k]}


def load_labels(path):
    return {(r["id"], r["run"], r["k"]): r["oracle"] for r in map(json.loads, open(path))}


def with_k(rows):
    """Index of each record within its episode, in file order (the key the oracle labels use)."""
    seen = defaultdict(int)
    for r in rows:
        key = (r.get("src", ""), r["id"], r["run"])
        r.setdefault("k", seen[key])
        seen[key] += 1
    return rows


def auroc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    if len(y) == 0 or y.min() == y.max():
        return float("nan")
    order = s.argsort(kind="mergesort")
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n0 * n1))


def prf(flag, y):
    flag, y = np.asarray(flag, bool), np.asarray(y, bool)
    tp = (flag & y).sum(); fp = (flag & ~y).sum(); fn = (~flag & y).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return float(p), float(r), float(2 * p * r / (p + r)) if p + r else 0.0


def pick_threshold(gold_scores, live_scores, live_y, max_gold=MAX_GOLD):
    gold_scores, live_scores, live_y = map(np.asarray, (gold_scores, live_scores, live_y))
    floor = float(np.quantile(gold_scores, 1 - max_gold)) if len(gold_scores) else -np.inf
    cands = np.unique(np.r_[live_scores, floor])
    cands = cands[cands >= floor]
    best, bt = -1.0, floor
    for t in cands:
        f1 = prf(live_scores > t, live_y)[2]
        if f1 > best:
            best, bt = f1, float(t)
    return bt


def report(items, t):
    """items: dicts with score, y, split, gold (bool). Returns per split metrics at threshold t."""
    out = {}
    for sp in ("train", "val"):
        g = [i for i in items if i["split"] == sp and i["gold"]]
        lv = [i for i in items if i["split"] == sp and not i["gold"]]
        s = np.array([i["score"] for i in lv]); y = np.array([i["y"] for i in lv])
        p, r, f1 = prf(s > t, y) if len(lv) else (np.nan,) * 3
        out[sp] = {"gold_ffr": float(np.mean([i["score"] > t for i in g])) if g else float("nan"),
                   "live_flag": float(np.mean(s > t)) if len(lv) else float("nan"),
                   "prec": p, "rec": r, "f1": f1, "auroc": auroc(s, y), "n_gold": len(g), "n_live": len(lv), "n_pos": int(y.sum()) if len(lv) else 0}
    return out


COLS = ["kind", "variant", "val_gold_ffr", "val_live_flag", "val_prec", "val_rec", "val_f1", "val_auroc", "train_gold_ffr", "train_f1", "train_auroc", "as_is_val_gold_ffr", "as_is_val_live_flag", "as_is_val_f1"]


def row(kind, variant, items, t, t_as_is=None):
    m = report(items, t)
    x = {"kind": kind, "variant": variant, "t": t, **{f"{sp}_{k}": v for sp in m for k, v in m[sp].items()}}
    if t_as_is is not None:
        a = report(items, t_as_is)["val"]
        x.update(as_is_val_gold_ffr=a["gold_ffr"], as_is_val_live_flag=a["live_flag"], as_is_val_f1=a["f1"])
    return x


def write_table(rows, path_md):
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    with open(path_md, "w") as f:
        f.write("| " + " | ".join(COLS) + " |\n|" + "---|" * len(COLS) + "\n")
        for x in sorted(rows, key=lambda x: (x["kind"], -np.nan_to_num(x.get("val_f1", 0)))):
            f.write("| " + " | ".join(fmt(x.get(c, "")) if c != "variant" else x["variant"][:80] for c in COLS) + " |\n")
