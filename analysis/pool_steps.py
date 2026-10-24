# Pool every recorded call step (our Qwen3.5 9B runs plus Shuban's Qwen3 8B live steps) with the narrow step labels of
# step_labels.py, split by scenario (split.json). Test scenarios are dropped. Writes one row per call: judge state, labels.
# usage: python analysis/pool_steps.py OUT.jsonl RUN_DIR [RUN_DIR ...]   (Shuban's finetune_data is always added)
import json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step_labels as S  # noqa: E402

SHUBAN = os.path.join(ROOT, "shuban_findings", "finetune_data")
HEADS = ("unneeded_irreversible", "wrong_irreversible", "made_up_value", "breaks_task")
SPLIT = {s: k for k, v in json.load(open(os.path.join(SHUBAN, "split.json"))).items() if k != "dropped" for s in v}


def labels(state, breaks):
    step, gold = state["step"], [S.parse(g) for g in (state.get("gold_turn") or [])]
    name, args = step.get("name"), {k: S.norm(v) for k, v in (step.get("args") or {}).items()}
    gold_names = {g[0] for g in gold}
    gold_vals = {x for _, ga in gold for v in ga.values() for x in S.flat_values(v)}
    irr = name in S.R.IRREVERSIBLE
    same = [ga for gn, ga in gold if gn == name]
    return {"unneeded_irreversible": int(irr and name not in gold_names),
            "wrong_irreversible": int(irr and bool(same) and not any(
                {k: S.norm(v) for k, v in ga.items() if not k.startswith("_")} == args for ga in same)),
            "made_up_value": int(any(src == "nowhere" and S.norm(val) not in gold_vals for _, val, src in step.get("ev", []))),
            "breaks_task": int(bool(breaks))}


def ours(d):
    states = {}
    for f in os.listdir(d):
        if f.startswith("states_"):
            for l in open(os.path.join(d, f)):
                r = json.loads(l)
                states.setdefault((r["id"], r["run"]), []).append(r)
    src = "q35_9b:" + os.path.basename(os.path.normpath(d))
    for l in open(os.path.join(d, "labels.jsonl")):
        lab = json.loads(l)
        if lab["kind"] == "call":
            yield src, states[(lab["id"], lab["run"])][lab["k"]], lab.get("off_track_subset", 0)


def shuban():
    for l in open(os.path.join(SHUBAN, "live_steps_labelled.jsonl")):
        r = json.loads(l)
        if r["step"]["kind"] == "call":
            yield "q3_8b", r, r.get("oracle_flag", 0)


def main():
    out, dirs = sys.argv[1], sys.argv[2:]
    cnt, n = Counter(), Counter()
    with open(out, "w") as f:
        for gen in [ours(d) for d in dirs] + [shuban()]:
            for src, st, brk in gen:
                split = SPLIT.get(int(st["id"].rsplit("_", 1)[1]))
                if split not in ("train", "val"):
                    continue
                lab = labels(st, brk)
                row = {"id": st["id"], "run": st["run"], "source": src, "split": split,
                       "state": {k: st[k] for k in ("requests", "plan", "recent", "step")}, **lab,
                       "bad": int(any(lab.values()))}
                f.write(json.dumps(row) + "\n")
                n[(src, split)] += 1
                for h in HEADS + ("bad",):
                    cnt[(src, split, h)] += row[h]
    print(f"{'source':22s} {'split':5s} {'calls':>6s} " + " ".join(f"{h[:12]:>12s}" for h in HEADS + ("bad",)))
    for src, split in sorted(n):
        print(f"{src:22s} {split:5s} {n[(src, split)]:6d} " + " ".join(f"{cnt[(src, split, h)]:12d}" for h in HEADS + ("bad",)))
    for split in ("train", "val"):
        tot = sum(v for (s, sp), v in n.items() if sp == split)
        print(f"{'ALL':22s} {split:5s} {tot:6d} " + " ".join(
            f"{sum(v for (s, sp, h2), v in cnt.items() if sp == split and h2 == h):12d}" for h in HEADS + ("bad",)))


if __name__ == "__main__":
    main()
