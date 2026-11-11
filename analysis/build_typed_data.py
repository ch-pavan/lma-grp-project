# Plan item 4.4 (analysis/2026-11-09_typed_closing_head.md): closing-message rows for a three-way Laya head
# (done / off track / false claim), from the done head's rows (same input text) and the LLM annotators' labels.
#   train.jsonl: the done head's train and dev rows (74 train scenarios), labels from DeepSeek and GLM under guide v3,
#                with a scenario-grouped fold (0..K-1) for out-of-fold thresholds.
#   val.jsonl:   the done head's val rows (15 val scenarios), with the v2 labels used by primary_val.py (reporting only).
# Each row keeps "y": [DeepSeek, GLM] class indices (0 done, 1 off track, 2 false claim), None where one gave no label.
# usage: python analysis/build_typed_data.py OUT_DIR [--k 5]
import argparse, json, os, random

CLASSES = ["done", "off_track", "false_claim"]
DONE_DIR = "runs/data/laya_done"
TRAIN_LABELS = ["runs/raw/test9b_labels/train/annot_v3_deepseek_turns.jsonl", "runs/raw/test9b_labels/train/annot_v3_glm_turns.jsonl"]
VAL_LABELS = ["runs/data/q9b_s1t_49146/val/annot_v2_deepseek.jsonl", "runs/data/q9b_s1t_49146/val/annot_v2_glm.jsonl"]


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def cls(answer):
    """The scoring map of offline_eval.annot_label: unsupported_claim is a false claim (on track for Q1), done is done,
    missing_action and should_ask_user are off track."""
    return {"done": 0, "missing_action": 1, "should_ask_user": 1, "unsupported_claim": 2}.get(answer)


def labels(paths):
    out = []
    for p in paths:
        d = {}
        for r in jl(p):
            if r.get("kind") == "turn" and cls(r.get("answer")) is not None:
                d[r["uid"]] = cls(r["answer"])
        out.append(d)
    return out


def attach(rows, labs):
    kept, missing = [], 0
    for r in rows:
        y = [d.get(r["uid"]) for d in labs]  # [DeepSeek, GLM], None where that annotator gave no label
        if all(v is None for v in y):
            missing += 1
            continue
        kept.append({"uid": r["uid"], "scenario": r["scenario"], "version": r["version"], "text": r["text"], "y": y,
                     "done_label": r["label"]})
    return kept, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir"); ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    train = jl(os.path.join(DONE_DIR, "train.jsonl")) + jl(os.path.join(DONE_DIR, "dev.jsonl"))
    tr, miss_tr = attach(train, labels(TRAIN_LABELS))
    va, miss_va = attach(jl(os.path.join(DONE_DIR, "val.jsonl")), labels(VAL_LABELS))
    scen = sorted({r["scenario"] for r in tr})
    random.Random(0).shuffle(scen)
    fold = {s: i % a.k for i, s in enumerate(scen)}
    for r in tr:
        r["fold"] = fold[r["scenario"]]
    for name, rows in (("train", tr), ("val", va)):
        with open(os.path.join(a.out_dir, f"{name}.jsonl"), "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    for name, rows, miss in (("train", tr, miss_tr), ("val", va, miss_va)):
        both = [r for r in rows if None not in r["y"]]
        per = [sum(1 for r in rows if c in r["y"]) for c in range(3)]
        agree = [sum(1 for r in both if r["y"] == [c, c]) for c in range(3)]
        print(f"{name}: {len(rows)} rows ({miss} without any label, {len(rows) - len(both)} with one), "
              + ", ".join(f"{CLASSES[c]} either {per[c]} both {agree[c]}" for c in range(3)))
    print("folds:", {k: sum(1 for r in tr if r["fold"] == k) for k in range(a.k)})


if __name__ == "__main__":
    main()
