# Score a Laya step check (val_scores.jsonl from train_laya_done.py --question step) against the plain rule "flag every
# irreversible call", overall and within the two parts the rule cannot split: irreversible calls (which of them are bad)
# and reads (bad reads are those that break the task). AUROC needs no threshold; F1 uses the dev threshold in results.json.
# usage: python analysis/eval_step.py STEP_DATA_DIR RUN_DIR
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step_labels as S  # noqa: E402
import train_laya_done as T  # noqa: E402


def name(text):
    return text.split("Proposed tool call: ", 1)[1].split("(", 1)[0]


def main():
    data_dir, run_dir = sys.argv[1:3]
    rows = {r["uid"]: r for r in map(json.loads, open(os.path.join(data_dir, "val.jsonl")))}
    sc = {r["uid"]: r["p_not_done"] for r in map(json.loads, open(os.path.join(run_dir, "val_scores.jsonl")))}
    thr = json.load(open(os.path.join(run_dir, "results.json")))["best"]["dev"]["threshold"]
    us = [u for u in rows if u in sc]
    irr = {u: int(name(rows[u]["text"]) in S.R.IRREVERSIBLE) for u in us}
    print(f"val calls {len(us)}, bad {sum(1 - rows[u]['label'] for u in us)}, dev threshold {thr:.3f}")
    print(f"  {'part':34s} {'n':>5s} {'bad':>4s}  {'rule AUROC':>10s} {'rule F1':>7s}  {'Laya AUROC':>10s} {'Laya F1':>7s}")
    for part, sel in (("all calls", us), ("irreversible calls", [u for u in us if irr[u]]), ("reads", [u for u in us if not irr[u]])):
        y = [1 - rows[u]["label"] for u in sel]
        rule, laya = [irr[u] for u in sel], [sc[u] for u in sel]
        rf = T.prf(y, [bool(x) for x in rule])[2]
        lf = T.prf(y, [x >= thr for x in laya])[2]
        ra = T.auroc(y, rule) if len(set(rule)) > 1 else 0.5
        print(f"  {part:34s} {len(sel):5d} {sum(y):4d}  {ra:10.3f} {rf:7.3f}  {T.auroc(y, laya):10.3f} {lf:7.3f}")
    for src in sorted({rows[u]["source"] for u in us}):
        sel = [u for u in us if rows[u]["source"] == src]
        y = [1 - rows[u]["label"] for u in sel]
        print(f"  by source {src:24s} {len(sel):5d} {sum(y):4d}  {T.auroc(y, [irr[u] for u in sel]):10.3f} {'':7s}  "
              f"{T.auroc(y, [sc[u] for u in sel]):10.3f}")


if __name__ == "__main__":
    main()
