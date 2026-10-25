# Proposal primary metric on val (mean F1 of Q1 off track and Q2 false claim), finetuned Laya against the 9B SLM judge, on
# all 1,772 steps of the 9B no judge run (q9b_s1t_49146): 1,277 calls and 495 closing messages. Scored with Shuban's
# offline_eval.py against the v2 DeepSeek and GLM labels and where the two agree.
#   Laya: step head (job 49656, dev threshold) gives Q1 on calls; done head (job 49265, threshold 0.5 as in the live runs)
#   gives Q2 on closing messages, P(not done) >= 0.5 -> false_claim, on track for Q1 (the live mapping).
#   9B SLM judge: offline_eval.py --judge llm --reasoning on (job 50247), Q1 and Q2 on every step. Unparsed -> on track, none.
# CIs: bootstrap over the 15 val scenarios, the same draws for both judges, so the difference is paired.
# usage: python analysis/primary_val.py [9B predictions.jsonl]
import collections, json, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shuban_findings", "code"))
import offline_eval as E  # noqa: E402

D = "runs/data/"
V = D + "q9b_s1t_49146/val/"
B = 10000
DONE_THR = 0.5


def laya_preds(rows):
    thr = json.load(open(D + "laya_runs/49656/results.json"))["best"]["dev"]["threshold"]
    step = {r["uid"]: r["p_not_done"] for r in map(json.loads, open(D + "laya_runs/49656/val_scores.jsonl"))}
    done = {E.uid_key(r["uid"])[0]: r["p_not_done"] for r in map(json.loads, open(D + "laya_runs/49265/val_scores.jsonl"))}
    calls = collections.defaultdict(list)
    for r in rows:
        if r["step"]["kind"] == "call":
            calls[(r["id"], r["run"])].append(r["k"])
    L = collections.defaultdict(list)
    for r in map(json.loads, open(D + "laya_step/val.jsonl")):
        if r["source"] == "q35_9b:val":
            _, i, run, g = r["uid"].split("|")
            L[(i, int(run))].append((int(g), step[r["uid"]]))
    out = {}
    for ep, ps in L.items():  # Laya rows are in pooled order; both list an episode's calls in order
        ks = sorted(calls[ep])
        assert len(ks) == len(ps), ep
        for k, (_, p) in zip(ks, sorted(ps)):
            out[ep + (k,)] = {"q1": "off_track" if p >= thr else "on_track", "q2": "none"}
    for key, p in done.items():
        out[key] = {"q1": "on_track", "q2": "false_claim" if p >= DONE_THR else "none"}
    return out


def nine_preds(path):
    return {(r["id"], r["run"], r["k"]): {"q1": r["q1"] if r.get("parsed") else "on_track", "q2": r["q2"] if r.get("parsed") else "none"}
            for r in map(json.loads, open(path))}


def f1_boot(keys, lab, pr, q, cls, scen, names, idx):
    per = E.conf_by_scenario([(scen[k], lab[k][q], pr[k][q], k) for k in keys], q, {})
    stack = np.stack([per.get(s, np.zeros((len(E.CLASSES[q]),) * 2)) for s in names])
    j = E.CLASSES[q].index(cls)
    p, r, f, sup = E.prf(stack.sum(0))
    return f[j], p[j], r[j], int(sup[j]), int(stack.sum(0)[:, j].sum()), np.array([E.prf(c)[2][j] for c in stack[idx].sum(1)])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else D + "q9b_slm_val/full/predictions.jsonl"
    rows = E.load_steps([V])
    scen = {(r["id"], r["run"], r["k"]): r["id"] for r in rows}
    ds, _ = E.load_label_set(V + "annot_v2_deepseek.jsonl", rows)
    gl, _ = E.load_label_set(V + "annot_v2_glm.jsonl", rows)
    both = {k: {q: v for q, v in ds[k].items() if gl.get(k, {}).get(q) == v} for k in ds}
    P = {"Laya finetuned": laya_preds(rows), "9B SLM judge": nine_preds(path)}
    common = set(P["Laya finetuned"]) & set(P["9B SLM judge"])
    print(f"steps: Laya {len(P['Laya finetuned'])}, 9B {len(P['9B SLM judge'])}, both {len(common)}\n")
    print("| labels | class | positives | judge | flags | precision | recall | F1 [95% CI] |\n|---|---|---|---|---|---|---|---|")
    summary = []
    for name, lab in (("DeepSeek v2", ds), ("GLM v2", gl), ("both agree", both)):
        names = sorted({scen[k] for k in common})
        idx = E.boot_idx(len(names), B)
        res = {}
        for q, cls in E.PRIMARY:
            keys = sorted(k for k in common if q in lab.get(k, {}))
            for jn, pr in P.items():
                f, p, r, sup, fl, bf = f1_boot(keys, lab, pr, q, cls, scen, names, idx)
                res[(jn, q)] = (f, bf)
                print(f"| {name} | {q} {cls} | {sup} | {jn} | {fl} | {p:.2f} | {r:.2f} | {f:.2f} [{np.percentile(bf, 2.5):.2f}, {np.percentile(bf, 97.5):.2f}] |")
        prim = {jn: (np.mean([res[(jn, q)][0] for q, _ in E.PRIMARY]), np.mean([res[(jn, q)][1] for q, _ in E.PRIMARY], 0)) for jn in P}
        d = prim["Laya finetuned"][1] - prim["9B SLM judge"][1]
        summary.append((name, prim, prim["Laya finetuned"][0] - prim["9B SLM judge"][0], d))
    print("\n| labels | Laya primary | 9B primary | Laya − 9B, F1 points [95% CI] |\n|---|---|---|---|")
    for name, prim, pt, d in summary:
        print(f"| {name} | {prim['Laya finetuned'][0]:.2f} | {prim['9B SLM judge'][0]:.2f} | "
              f"{pt * 100:+.1f} [{np.percentile(d, 2.5) * 100:+.1f}, {np.percentile(d, 97.5) * 100:+.1f}] |")
    print("\nProposal bar: Laya ahead by at least 9 points with the CI above 0.")


if __name__ == "__main__":
    main()
