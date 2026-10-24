# Feature trees classifier from scratch: hand built step features -> oracle label. Fit on train scenarios, report val.
# usage: python hand_clf.py GOLD_STATES LIVE_STATES ORACLE_LABELS OUTDIR
import json, os, sys
from collections import defaultdict
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import laya_metrics as M
import tree_judge as T

gold_p, live_p, lab_p, outdir = sys.argv[1:5]
labels = M.load_labels(lab_p)


def load(path, gold):
    rows = [json.loads(l) for l in open(path)]
    kt = defaultdict(int)
    per_ep = defaultdict(int)
    out = []
    for r in rows:
        k = per_ep[(r["id"], r["run"])]; per_ep[(r["id"], r["run"])] += 1
        kk = kt[(r["id"], r["run"], r["turn"])]; kt[(r["id"], r["run"], r["turn"])] += 1
        y = 0 if gold else labels.get((r["id"], r["run"], k))
        if y is None:
            continue
        step = dict(r["step"]); step["ev"] = [tuple(e) for e in step.get("ev") or []]
        out.append({"x": T.featurize(step, r["plan"], [tuple(x) for x in r["recent"]], kk, r["n_recent"]), "y": y, "gold": gold,
                    "kind": step["kind"], "split": M.SPLIT_OF[r["scenario"]]})
    return out


items = load(gold_p, True) + load(live_p, False)
tr = [i for i in items if i["split"] == "train"]
X = np.array([i["x"] for i in tr]); y = np.array([i["y"] for i in tr])
clf = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, class_weight="balanced", random_state=0).fit(X, y)


def export(clf):
    trees = []
    for preds in clf._predictors:
        nodes = preds[0].nodes
        trees.append([{"leaf": bool(n["is_leaf"]), "f": int(n["feature_idx"]), "thr": float(n["num_threshold"]),
                       "left": int(n["left"]), "right": int(n["right"]), "value": float(n["value"])} for n in nodes])
    return {"baseline": float(np.ravel(clf._baseline_prediction)[0]), "trees": trees, "features": T.NAMES}


model = export(clf)
Z = np.array([T.tree_predict(model, i["x"]) for i in items])
ref = clf.decision_function(np.array([i["x"] for i in items]))
assert np.allclose(Z, ref, atol=1e-6), "exported trees disagree with sklearn"
for i, z in zip(items, Z):
    i["score"] = float(z)
model["t"] = {}
rows = []
for kind in ("call", "msg"):
    it = [i for i in items if i["kind"] == kind]
    trn = [i for i in it if i["split"] == "train"]
    t = M.pick_threshold([i["score"] for i in trn if i["gold"]], [i["score"] for i in trn if not i["gold"]], [i["y"] for i in trn if not i["gold"]])
    model["t"][kind] = t
    rows.append(M.row(kind, "feature trees (hand features, from scratch)", it, t))
os.makedirs(outdir, exist_ok=True)
json.dump(model, open(os.path.join(outdir, "tree_model.json"), "w"))
json.dump(rows, open(os.path.join(outdir, "tree_rows.json"), "w"), indent=1)
print("trees", len(model["trees"]), "thresholds", model["t"])
for r in rows:
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in M.COLS or k.startswith("val_n")})
