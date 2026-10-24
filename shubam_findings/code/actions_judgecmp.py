# Judge models on identical recorded steps against oracle labels (laya_labels.py output).
# usage: python3 actions_judgecmp.py LABELS.jsonl JUDGE1.jsonl [JUDGE2.jsonl ...]
import json, os, sys
import numpy as np


def load(p):
    return {(r["id"], r["run"], r["k"]): r for r in map(json.loads, open(p)) if r}


def auroc(y, s):
    y, s = np.array(y), np.array(s)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


lab = load(sys.argv[1])
print("| judge | kind | steps | oracle flags | judge flags | precision | recall | AUROC p_flag | parsed % | out tok/step |")
print("|---|---|---|---|---|---|---|---|---|---|")
for p in sys.argv[2:]:
    J = load(p)
    for kind in ("call", "msg", "all"):
        ks = [k for k in J if k in lab and (kind == "all" or J[k]["kind"] == kind)]
        if not ks:
            continue
        y = [lab[k]["oracle"] for k in ks]
        f = [J[k]["flag"] for k in ks]
        tp = sum(a and b for a, b in zip(y, f))
        prec = tp / max(sum(f), 1)
        rec = tp / max(sum(y), 1)
        print(f"| {os.path.basename(p)} | {kind} | {len(ks)} | {sum(y)} | {sum(f)} | {prec:.2f} | {rec:.2f} | "
              f"{auroc(y, [J[k]['p_flag'] for k in ks]):.2f} | {100*np.mean([bool(J[k]['parsed']) for k in ks]):.0f} | {np.mean([J[k]['jout'] for k in ks]):.0f} |")
