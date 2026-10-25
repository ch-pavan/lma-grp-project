# Primary metric, off track half, on the 1,277 val calls of the 9B no judge run (q9b_s1t_49146): finetuned Laya step head
# (job 49656, dev threshold) against the 9B as SLM judge (offline_9b_steps.jsonl from job 49671/49688), both scored with
# Shuban's offline_eval.py against the v2 DeepSeek and GLM labels and where the two agree. The difference is a paired
# bootstrap over scenarios (same draws for both judges). Unparsed 9B answers count as on track (the judge did not flag).
# usage: python analysis/primary_val_calls.py
import collections, json, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shuban_findings", "code"))
import offline_eval as E  # noqa: E402

D = "runs/data/"
V = D + "q9b_s1t_49146/val/"
B = 10000


def preds():
    thr = json.load(open(D + "laya_runs/49656/results.json"))["best"]["dev"]["threshold"]
    sc = {r["uid"]: r["p_not_done"] for r in map(json.loads, open(D + "laya_runs/49656/val_scores.jsonl"))}
    nine, L = {}, collections.defaultdict(list)
    for r in map(json.loads, open(D + "q9b_rb_49671/offline_9b_steps.jsonl")):
        key, _ = E.uid_key(r["uid"])
        nine[key] = {"q1": r["q1"] or "on_track"}
    for r in map(json.loads, open(D + "laya_step/val.jsonl")):
        if r["source"] == "q35_9b:val":
            _, i, run, g = r["uid"].split("|")
            L[(i, int(run))].append((int(g), sc[r["uid"]]))
    # Laya rows are in pooled order, the 9B rows carry the state index k; both list an episode's calls in order.
    ks = collections.defaultdict(list)
    for key in nine:
        ks[key[:2]].append(key[2])
    laya = {}
    for ep, rows in L.items():
        k = sorted(ks[ep])
        assert len(k) == len(rows), ep
        for kk, (_, p) in zip(k, sorted(rows)):
            laya[ep + (kk,)] = {"q1": "off_track" if p >= thr else "on_track"}
    return {"Laya finetuned": laya, "9B SLM judge": nine}


def main():
    rows = E.load_steps([V])
    scen = {(r["id"], r["run"], r["k"]): r["id"] for r in rows}
    kind = {(r["id"], r["run"], r["k"]): r["step"]["kind"] for r in rows}
    ds, _ = E.load_label_set(V + "annot_v2_deepseek.jsonl", rows)
    gl, _ = E.load_label_set(V + "annot_v2_glm.jsonl", rows)
    both = {k: {"q1": v["q1"]} for k, v in ds.items() if "q1" in v and gl.get(k, {}).get("q1") == v["q1"]}
    P = preds()
    assert all(kind[k] == "call" for p in P.values() for k in p)
    cl = E.CLASSES["q1"]; j = cl.index("off_track")
    print("Q1 off track on val calls; CIs: bootstrap over the 15 val scenarios, paired for the difference\n")
    print(f"| labels | calls | off track | judge | flags | precision | recall | F1 [95% CI] |")
    print("|---|---|---|---|---|---|---|---|")
    diffs = {}
    for name, lab in (("DeepSeek v2", ds), ("GLM v2", gl), ("both agree", both)):
        keys = sorted(k for k in P["Laya finetuned"] if k in lab and "q1" in lab[k])
        names = sorted({scen[k] for k in keys})
        idx = E.boot_idx(len(names), B)
        boots = {}
        for jn, pr in P.items():
            per = E.conf_by_scenario([(scen[k], lab[k]["q1"], pr[k]["q1"], k) for k in keys], "q1", {})
            stack = np.stack([per[s] for s in names])
            p, r, f, sup = E.prf(stack.sum(0))
            bf = np.array([E.prf(c)[2][j] for c in stack[idx].sum(1)])
            boots[jn] = bf
            print(f"| {name} | {len(keys)} | {int(sup[j])} | {jn} | {int(stack.sum(0)[:, j].sum())} | {p[j]:.2f} | {r[j]:.2f} | "
                  f"{f[j]:.2f} [{np.percentile(bf, 2.5):.2f}, {np.percentile(bf, 97.5):.2f}] |")
            boots[jn + "_point"] = f[j]
        d = boots["Laya finetuned"] - boots["9B SLM judge"]
        diffs[name] = (boots["Laya finetuned_point"] - boots["9B SLM judge_point"], np.percentile(d, 2.5), np.percentile(d, 97.5))
    print("\nLaya minus 9B, F1 points [95% CI]  (proposal bar: +9 with the CI above 0)")
    for n, (pt, lo, hi) in diffs.items():
        print(f"  {n:12s} {pt * 100:+5.1f} [{lo * 100:+.1f}, {hi * 100:+.1f}]")


if __name__ == "__main__":
    main()
