# The proposal's primary comparison on the labelled test steps (sample_order.txt, 7,214 steps of the 8 test passes):
# mean F1 of Q1 off track and Q2 false claim against the guide v3 labels of DeepSeek, of GLM and where both agree, with a
# paired bootstrap over the test scenarios. Systems:
#   9B SLM judge: offline_eval.py --judge llm --reasoning on, merged with the 8,192 token rejudge; unparsed -> on track, none
#   Laya frozen:  step head orig_seed1 at 0.1266 on calls; done head 64348, P(not done) >= 0.561 -> false claim (the
#                 proposal's mapping, as in the mid report)
#   Laya typed:   the same step head on calls; the item 4.4 head on closing messages, with its out-of-fold thresholds
#                 (a change after the freeze, reported next to the frozen Laya)
# usage: python analysis/primary_test.py TEST_DIR SAMPLE LABEL_DIR JUDGE_DIR LAYA_TEST_SCORES THRESHOLDS.json
import argparse, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primary_val as PV  # noqa: E402
E = PV.E
STEP_THR, DONE_THR = 0.1266, 0.561


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    for x in ("test_dir", "sample", "label_dir", "judge_dir", "laya", "thresholds"):
        ap.add_argument(x)
    a = ap.parse_args()
    keys = set()
    for l in open(a.sample):
        if l.strip():
            i, r, k, _ = l.strip().split("|"); keys.add((i, int(r), int(k)))
    rows = [r for r in E.load_steps([a.test_dir]) if (r["id"], r["run"], r["k"]) in keys]
    # bootstrap unit: the scenario number, shared by its 4 versions (multi_turn_base_33, multi_turn_miss_func_33, ...)
    scen = {(r["id"], r["run"], r["k"]): r["id"].rsplit("_", 1)[1] for r in rows}
    kind = {(r["id"], r["run"], r["k"]): r["step"]["kind"] for r in rows}
    ds, _ = E.load_label_set(os.path.join(a.label_dir, "annot_v3_deepseek.jsonl"), rows)
    gl, _ = E.load_label_set(os.path.join(a.label_dir, "annot_v3_glm.jsonl"), rows)
    both = {k: {q: v for q, v in ds[k].items() if gl.get(k, {}).get(q) == v} for k in ds}

    nine = {(r["id"], r["run"], r["k"]): r for r in jl(os.path.join(a.judge_dir, "full", "predictions.jsonl"))}
    for r in jl(os.path.join(a.judge_dir, "pass2.jsonl")):
        nine[(r["id"], r["run"], r["k"])] = r
    unparsed = sum(1 for k in keys if not nine.get(k, {}).get("parsed"))
    P = {"9B SLM judge": {k: {"q1": r["q1"] if r.get("parsed") else "on_track", "q2": r["q2"] if r.get("parsed") else "none"}
                          for k, r in nine.items() if k in keys}}
    thr = json.load(open(a.thresholds))
    fr, ty = {}, {}
    for r in jl(a.laya):
        k = (r["id"], r["run"], r["k"])
        if r["kind"] == "call":
            v = {"q1": "off_track" if r["p_bad"] >= STEP_THR else "on_track", "q2": "none"}
            fr[k] = ty[k] = v
        else:
            fr[k] = {"q1": "on_track", "q2": "false_claim" if r["p_not_done"] >= DONE_THR else "none"}
            p = r["p_typed"]
            ty[k] = ({"q1": "on_track", "q2": "false_claim"} if p[2] >= thr["t_fc"] else
                     {"q1": "off_track", "q2": "none"} if p[1] >= thr["t_off"] else {"q1": "on_track", "q2": "none"})
    P["Laya frozen"], P["Laya typed (after freeze)"] = fr, ty
    common = keys & set.intersection(*map(set, P.values()))
    print(f"test steps: {len(keys)} sampled, {len(common)} scored by every system "
          f"({sum(kind[k] == 'call' for k in common)} calls, {sum(kind[k] == 'msg' for k in common)} closing messages); "
          f"9B unparsed after the rejudge {unparsed}; {len({scen[k] for k in common})} scenarios\n")

    print("| labels | system | off track F1 | false claim F1 | primary | − 9B, F1 points [95% CI] | − Laya frozen [95% CI] |\n|---|---|---|---|---|---|---|")
    for name, lab in (("DeepSeek v3", ds), ("GLM v3", gl), ("both agree", both)):
        names = sorted({scen[k] for k in common}); idx = E.boot_idx(len(names), PV.B)
        res = {}
        for jn, pr in P.items():
            fs = []
            for q, cls in E.PRIMARY:
                ks = sorted(k for k in common if q in lab.get(k, {}))
                f, p, rc, sup, fl, bf = PV.f1_boot(ks, lab, pr, q, cls, scen, names, idx)
                fs.append((f, bf, sup))
            res[jn] = (fs, np.mean([x[0] for x in fs]), np.mean([x[1] for x in fs], 0))
        for jn in P:
            cells = []
            for ref in ("9B SLM judge", "Laya frozen"):
                if jn == ref or (ref == "Laya frozen" and jn == "9B SLM judge"):
                    cells.append("")
                    continue
                d = res[jn][2] - res[ref][2]
                cells.append(f"{(res[jn][1] - res[ref][1]) * 100:+.1f} [{np.percentile(d, 2.5) * 100:+.1f}, {np.percentile(d, 97.5) * 100:+.1f}]")
            (fo, _, so), (fc, _, sc) = res[jn][0]
            print(f"| {name} | {jn} | {fo:.2f} ({so}) | {fc:.2f} ({sc}) | {res[jn][1]:.3f} | {cells[0]} | {cells[1]} |")
    print("\nPositives in brackets. Proposal bar: Laya ahead of the 9B by at least 9 points with the CI above 0.")

    print("\n| labels | steps | off track positives | 9B F1 | Laya frozen F1 | Laya typed F1 |\n|---|---|---|---|---|---|")
    for name, lab in (("DeepSeek v3", ds), ("GLM v3", gl), ("both agree", both)):
        for sub in ("call", "msg"):
            ks = sorted(k for k in common if kind[k] == sub and "q1" in lab.get(k, {}))
            names = sorted({scen[k] for k in ks}); idx = E.boot_idx(len(names), 200)
            f = {jn: PV.f1_boot(ks, lab, pr, "q1", "off_track", scen, names, idx) for jn, pr in P.items()}
            print(f"| {name} | {'tool calls' if sub == 'call' else 'closing messages'} | {f['9B SLM judge'][3]} | "
                  + " | ".join(f"{f[jn][0]:.2f}" for jn in P) + " |")


if __name__ == "__main__":
    main()
