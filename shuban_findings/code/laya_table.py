# Score laya sweep features against oracle labels, fit a small logistic head (train scenarios only), write the
# shared table (merging tree_rows.json / jev_rows.json found in OUTDIR) and the online laya configs.
# usage: python laya_table.py LABELS OUTDIR FEATS.jsonl [FEATS2.jsonl ...]
import json, math, os, sys
import numpy as np
import laya_metrics as M

lab_p, outdir, *feat_ps = sys.argv[1:]
labels = M.load_labels(lab_p)
rows = []
for p in feat_ps:
    rows += M.with_k([json.loads(l) for l in open(p)])
items = []
for r in rows:
    gold = r["src"].startswith("gold")
    y = 0 if gold else labels.get((r["id"], r["run"], r["k"]))
    if y is None:
        continue
    items.append({"f": r["f"], "y": y, "gold": gold, "kind": r["step"]["kind"], "split": M.SPLIT_OF[r["scenario"]]})


def lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def fit_logreg(X, y, l2=1.0, iters=100):
    X1 = np.hstack([X, np.ones((len(X), 1))]); w = np.zeros(X1.shape[1])
    cw = np.where(y == 1, 0.5 / max(y.mean(), 1e-9), 0.5 / max(1 - y.mean(), 1e-9))
    reg = l2 * np.r_[np.ones(len(w) - 1), 0]
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X1 @ w))
        g = X1.T @ (cw * (p - y)) + reg * w
        H = (X1 * (cw * p * (1 - p))[:, None]).T @ X1 + np.diag(reg) + 1e-6 * np.eye(len(w))
        st = np.linalg.solve(H, g); w -= st
        if np.abs(st).max() < 1e-6:
            break
    return w[:-1], float(w[-1])


table, parts = [], {}
for kind in ("call", "msg"):
    it = [i for i in items if i["kind"] == kind]
    if not it:
        continue
    keys = sorted(set.intersection(*[set(i["f"]) for i in it]))
    trn = [i for i in it if i["split"] == "train"]
    trg = [i for i in trn if i["gold"]]; trl = [i for i in trn if not i["gold"]]
    best = None
    for k in keys:
        for i in it:
            i["score"] = i["f"][k]
        t = M.pick_threshold([i["score"] for i in trg], [i["score"] for i in trl], [i["y"] for i in trl])
        x = M.row(kind, k if k.startswith("jev:") else "laya " + k, it, t, t_as_is=0.5)
        table.append(x)
        if best is None or x["train_f1"] > best[1]["train_f1"]:
            best = (k, x)
    parts["single_" + kind] = {"feats": [best[0]], "w": [1.0], "b": 0.0, "t": lg(best[1]["t"])}
    top = sorted(keys, key=lambda k: -np.nan_to_num(M.auroc([i["f"][k] for i in trn], [i["y"] for i in trn])))[:8]
    X = np.array([[lg(i["f"][k]) for k in top] for i in trn]); y = np.array([i["y"] for i in trn], float)
    w, b = fit_logreg(X, y)
    for i in it:
        i["score"] = b + sum(wi * lg(i["f"][k]) for wi, k in zip(w, top))
    t = M.pick_threshold([i["score"] for i in trg], [i["score"] for i in trl], [i["y"] for i in trl])
    table.append(M.row(kind, ("jev" if top[0].startswith("jev:") else "laya") + " head " + ",".join(top), it, t))
    parts["head_" + kind] = {"feats": top, "w": [float(v) for v in w], "b": b, "t": t}

cfgs = [{"name": n, "call": parts.get(n + "_call"), "msg": parts.get(n + "_msg")} for n in ("single", "head")]
os.makedirs(outdir, exist_ok=True)
json.dump(cfgs, open(os.path.join(outdir, "configs.json"), "w"), indent=1)
for extra in ("tree_rows.json", "jev_rows.json"):
    p = os.path.join(outdir, extra)
    if os.path.exists(p):
        table += json.load(open(p))
json.dump(table, open(os.path.join(outdir, "table.json"), "w"), indent=1)
M.write_table(table, os.path.join(outdir, "table.md"))
print(open(os.path.join(outdir, "table.md")).read())
print("configs:", json.dumps(cfgs)[:600])
