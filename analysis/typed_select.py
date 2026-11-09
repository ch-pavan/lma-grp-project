# Plan item 4.4 (analysis/2026-11-09_typed_closing_head.md), after training:
#   thresholds: pooled out-of-fold scores of the 5 fold runs -> t_fc (mean F1 against DeepSeek and GLM), then t_off on the
#               rows not called false claim. Written to OUT/thresholds.json.
#   validation: each full run (seed) with those thresholds and the frozen step head on calls, against the frozen Laya and
#               the 9B SLM judge, on the 1,772 val steps with the v2 labels, as primary_val.py. The run with the highest
#               mean primary over the three label sets is the one to freeze (OUT/choice.json).
# usage: python analysis/typed_select.py OUT --oof FOLD_DIR... --runs RUN_DIR... --done-scores FROZEN_DONE_VAL_SCORES
import argparse, collections, gzip, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primary_val as PV  # noqa: E402
E = PV.E

STEP_SCORES = "runs/data/laya_runs/ada_step_nobt/orig_seed1/val_scores.jsonl.gz"
STEP_THR = 0.1266
DONE_THR = 0.561


def jl(p):
    with (gzip.open(p, "rt") if p.endswith(".gz") else open(p)) as f:
        return [json.loads(l) for l in f if l.strip()]


def f1(y, pred):
    tp = sum(a and b for a, b in zip(y, pred)); fp = sum((not a) and b for a, b in zip(y, pred))
    fn = sum(a and not b for a, b in zip(y, pred))
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def mean_f1(rows, cls, pred):
    """Mean over the two annotators of F1 for class cls; each annotator only on the rows it labelled."""
    out = []
    for j in (0, 1):
        idx = [i for i, r in enumerate(rows) if r["y"][j] is not None]
        out.append(f1([rows[i]["y"][j] == cls for i in idx], [pred[i] for i in idx]))
    return float(np.mean(out))


def best_thr(rows, p, cls, allowed):
    cands = sorted(set(np.round(p[allowed], 4)))
    best = (-1.0, 1.0)
    for t in cands:
        f = mean_f1(rows, cls, list((p >= t) & allowed))
        if f > best[0]:
            best = (f, float(t))
    return best


def thresholds(fold_dirs):
    rows = [r for d in fold_dirs for r in jl(os.path.join(d, "scores.jsonl"))]
    P = np.array([r["p"] for r in rows])
    f_fc, t_fc = best_thr(rows, P[:, 2], 2, np.ones(len(rows), bool))
    f_off, t_off = best_thr(rows, P[:, 1], 1, P[:, 2] < t_fc)
    return {"t_fc": t_fc, "t_off": t_off, "oof_f1_fc": round(f_fc, 4), "oof_f1_off": round(f_off, 4), "oof_rows": len(rows)}


def step_preds(rows):
    step = {r["uid"]: r["p_not_done"] for r in jl(STEP_SCORES)}
    calls = collections.defaultdict(list)
    for r in rows:
        if r["step"]["kind"] == "call":
            calls[(r["id"], r["run"])].append(r["k"])
    L = collections.defaultdict(list)
    for r in jl(PV.D + "laya_step/val.jsonl"):
        if r["source"] == "q35_9b:val":
            _, i, run, g = r["uid"].split("|")
            L[(i, int(run))].append((int(g), step[r["uid"]]))
    out = {}
    for ep, ps in L.items():
        ks = sorted(calls[ep])
        assert len(ks) == len(ps), ep
        for k, (_, p) in zip(ks, sorted(ps)):
            out[ep + (k,)] = {"q1": "off_track" if p >= STEP_THR else "on_track", "q2": "none"}
    return out


def frozen_preds(rows, done_scores):
    out = step_preds(rows)
    for r in jl(done_scores):
        out[E.uid_key(r["uid"])[0]] = {"q1": "on_track", "q2": "false_claim" if r["p_not_done"] >= DONE_THR else "none"}
    return out


def typed_preds(rows, run_dir, thr):
    out = step_preds(rows)
    for r in jl(os.path.join(run_dir, "scores.jsonl")):
        p = r["p"]
        if p[2] >= thr["t_fc"]:
            v = {"q1": "on_track", "q2": "false_claim"}
        elif p[1] >= thr["t_off"]:
            v = {"q1": "off_track", "q2": "none"}
        else:
            v = {"q1": "on_track", "q2": "none"}
        out[E.uid_key(r["uid"])[0]] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--oof", nargs="+", required=True); ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--done-scores", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    thr = thresholds(a.oof)
    print("thresholds (out of fold on train):", thr, flush=True)
    json.dump(thr, open(os.path.join(a.out, "thresholds.json"), "w"), indent=1)

    rows = E.load_steps([PV.V])
    scen = {(r["id"], r["run"], r["k"]): r["id"] for r in rows}
    ds, _ = E.load_label_set(PV.V + "annot_v2_deepseek.jsonl", rows)
    gl, _ = E.load_label_set(PV.V + "annot_v2_glm.jsonl", rows)
    both = {k: {q: v for q, v in ds[k].items() if gl.get(k, {}).get(q) == v} for k in ds}
    P = {"9B SLM judge": PV.nine_preds(PV.D + "q9b_slm_val/merged.jsonl"), "Laya frozen": frozen_preds(rows, a.done_scores)}
    for d in a.runs:
        P["typed " + os.path.basename(d.rstrip("/"))] = typed_preds(rows, d, thr)
    common = set.intersection(*map(set, P.values()))
    print(f"\nval steps scored by every system: {len(common)}\n")
    print("| labels | system | off track F1 | false claim F1 | primary | − 9B [95% CI] | − frozen [95% CI] |\n|---|---|---|---|---|---|---|")
    mean_prim = collections.defaultdict(list)
    for name, lab in (("DeepSeek v2", ds), ("GLM v2", gl), ("both agree", both)):
        names = sorted({scen[k] for k in common}); idx = E.boot_idx(len(names), PV.B)
        res = {}
        for jn, pr in P.items():
            fs = []
            for q, cls in E.PRIMARY:
                keys = sorted(k for k in common if q in lab.get(k, {}))
                f, *_, bf = PV.f1_boot(keys, lab, pr, q, cls, scen, names, idx)
                fs.append((f, bf))
            res[jn] = (fs, np.mean([x[0] for x in fs]), np.mean([x[1] for x in fs], 0))
            mean_prim[jn].append(res[jn][1])
        for jn in P:
            (fo, _), (fc, _) = res[jn][0]
            cells = []
            for ref in ("9B SLM judge", "Laya frozen"):
                if jn == ref:
                    cells.append("")
                    continue
                d = res[jn][2] - res[ref][2]
                cells.append(f"{(res[jn][1] - res[ref][1]) * 100:+.1f} [{np.percentile(d, 2.5) * 100:+.1f}, {np.percentile(d, 97.5) * 100:+.1f}]")
            print(f"| {name} | {jn} | {fo:.2f} | {fc:.2f} | {res[jn][1]:.3f} | {cells[0]} | {cells[1]} |")
    typed = {jn: float(np.mean(v)) for jn, v in mean_prim.items() if jn.startswith("typed ")}
    pick = max(typed, key=typed.get)
    print("\nmean primary over the three label sets:", {k: round(float(np.mean(v)), 4) for k, v in mean_prim.items()})
    print("CHOICE:", pick)
    json.dump({"choice": pick.removeprefix("typed "), "mean_primary": typed, "thresholds": thr},
              open(os.path.join(a.out, "choice.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
