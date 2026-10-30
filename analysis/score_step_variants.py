# Plan item 3.7: score step-head runs trained with and without the oracle "breaks_task" label (runs/ada/laya_step_nobt.sbatch).
# For every run dir (results.json + val_scores.jsonl from train_laya_done.py --question step):
#   - AUROC and F1 (the run's own dev threshold) on the 2,427 pooled val calls, against the replay labels WITH breaks_task
#     and WITHOUT it (unneeded irreversible, or a made-up value on an irreversible call);
#   - AUROC and F1 with breaks_task on the 1,277 calls of the 9B val run only (109 bad), as in the mid report's offline table;
#   - F1 for Q1 off track on the 1,277 calls of the 9B val run against the v2 LLM annotators (A = DeepSeek V4.1 Flash,
#     B = GLM-5.3-Flash, and where both agree), mapped to steps as in analysis/primary_val.py.
# Then mean and standard deviation over the seeds of each variant (run names <variant>_seed<k>).
# usage (from inside an unpacked repo root, as for primary_val.py):
#   python analysis/score_step_variants.py RESULTS_DIR [--out FILE.md]    e.g. runs/data/laya_runs/ada_step_nobt
import argparse, collections, glob, json, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shuban_findings", "code"))
import offline_eval as E  # noqa: E402

D = "runs/data/"
V = D + "q9b_s1t_49146/val/"
IRREVERSIBLE = E.IRREVERSIBLE


def auroc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):  # average ranks for ties
        m = allv == v
        ranks[m] = ranks[m].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def f1(y, pred):
    y, pred = np.asarray(y, bool), np.asarray(pred, bool)
    tp = (y & pred).sum(); fp = (~y & pred).sum(); fn = (y & ~pred).sum()
    return float(2 * tp / (2 * tp + fp + fn)) if tp else 0.0


def name(text):
    return text.split("Proposed tool call: ", 1)[1].split("(", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir"); ap.add_argument("--out")
    a = ap.parse_args()
    val = [json.loads(l) for l in open(D + "laya_step/val.jsonl")]
    y_orig = {r["uid"]: 1 - r["label"] for r in val}  # 1 = bad
    y_nobt = {r["uid"]: int(bool(r["unneeded_irreversible"] or (r["made_up_value"] and name(r["text"]) in IRREVERSIBLE)))
              for r in val}
    rows = E.load_steps([V])
    ds, _ = E.load_label_set(V + "annot_v2_deepseek.jsonl", rows)
    gl, _ = E.load_label_set(V + "annot_v2_glm.jsonl", rows)
    calls = collections.defaultdict(list)
    for r in rows:
        if r["step"]["kind"] == "call":
            calls[(r["id"], r["run"])].append(r["k"])
    nine = collections.defaultdict(list)  # 9B val rows of the pooled val set, by episode, in pooled order
    for r in val:
        if r["source"] == "q35_9b:val":
            _, i, run, g = r["uid"].split("|")
            nine[(i, int(run))].append((int(g), r["uid"]))
    uid2key = {}
    for ep, us in nine.items():
        ks = sorted(calls[ep]); assert len(ks) == len(us), ep
        for k, (_, u) in zip(ks, sorted(us)):
            uid2key[u] = ep + (k,)

    runs = sorted(d for d in glob.glob(os.path.join(a.results_dir, "*")) if os.path.exists(os.path.join(d, "val_scores.jsonl")))
    per = collections.defaultdict(list)
    head = ("| {} | AUROC with bt | AUROC without bt | F1 with bt | F1 without bt | 9B calls AUROC | 9B calls F1 "
            "| off-track F1 vs A | vs B | vs both |\n|---|---|---|---|---|---|---|---|---|---|")
    lines = [head.format("run")]
    for d in runs:
        run = os.path.basename(d)
        thr = json.load(open(os.path.join(d, "results.json")))["best"]["dev"]["threshold"]
        sc = {r["uid"]: r["p_not_done"] for r in map(json.loads, open(os.path.join(d, "val_scores.jsonl")))}
        u = sorted(sc)
        m = {"auc_bt": auroc([y_orig[x] for x in u], [sc[x] for x in u]),
             "auc_nobt": auroc([y_nobt[x] for x in u], [sc[x] for x in u]),
             "f1_bt": f1([y_orig[x] for x in u], [sc[x] >= thr for x in u]),
             "f1_nobt": f1([y_nobt[x] for x in u], [sc[x] >= thr for x in u])}
        u9 = sorted(uid2key)
        m["auc_9b"] = auroc([y_orig[x] for x in u9], [sc[x] for x in u9])
        m["f1_9b"] = f1([y_orig[x] for x in u9], [sc[x] >= thr for x in u9])
        for nm, lab in (("A", ds), ("B", gl), ("both", None)):
            ys, ps = [], []
            for x, key in uid2key.items():
                if lab is None:
                    a1, b1 = ds.get(key, {}).get("q1"), gl.get(key, {}).get("q1")
                    if a1 is None or a1 != b1:
                        continue
                    gold = a1
                else:
                    gold = lab.get(key, {}).get("q1")
                    if gold is None:
                        continue
                ys.append(gold == "off_track"); ps.append(sc[x] >= thr)
            m[f"ot_{nm}"] = f1(ys, ps)
        variant = run.rsplit("_seed", 1)[0]
        per[variant].append(m)
        lines.append(f"| {run} | {m['auc_bt']:.3f} | {m['auc_nobt']:.3f} | {m['f1_bt']:.3f} | {m['f1_nobt']:.3f} | "
                     f"{m['auc_9b']:.3f} | {m['f1_9b']:.3f} | {m['ot_A']:.3f} | {m['ot_B']:.3f} | {m['ot_both']:.3f} |")
    lines += ["", head.format("variant (seeds)")]
    for v, ms in sorted(per.items()):
        cell = lambda k: f"{np.mean([x[k] for x in ms]):.3f} ± {np.std([x[k] for x in ms], ddof=1) if len(ms) > 1 else 0:.3f}"
        lines.append(f"| {v} ({len(ms)}) | " + " | ".join(cell(k) for k in ("auc_bt", "auc_nobt", "f1_bt", "f1_nobt", "auc_9b", "f1_9b", "ot_A", "ot_B", "ot_both")) + " |")
    text = "\n".join(lines)
    print(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
