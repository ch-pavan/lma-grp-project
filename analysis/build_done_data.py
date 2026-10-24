# Turn end examples for the Laya done check: one row per turn end with the oracle label (done 1, not done 0).
# State text puts what matters most first, since Laya keeps the start of a long state and cuts the end:
# closing message, latest request, this turn's calls (newest first, outputs cut short), earlier requests.
# usage: python analysis/build_done_data.py OUT_DIR TRAIN_RUN_DIR VAL_RUN_DIR [--dev-scenarios 8]
import argparse, json, os, random
from collections import defaultdict


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def state_text(requests, calls, closing, out_chars=200):
    lines = ["Closing message to the user: " + closing.strip(), "", "Latest user request: " + requests[-1].strip(), "",
             "Tool calls the agent ran for the latest request, newest first:"]
    lines += [f"- {c['call']} -> {str(c.get('out', ''))[:out_chars]}" for c in reversed(calls)] or ["- (none)"]
    if len(requests) > 1:
        lines += ["", "Earlier user requests, newest first:"] + [f"- {r.strip()}" for r in reversed(requests[:-1])]
    return "\n".join(lines)


def rows(run_dir, split):
    states, steps = defaultdict(list), {}
    for f in os.listdir(run_dir):
        if f.startswith("states_"):
            for r in jl(os.path.join(run_dir, f)):
                states[(r["id"], r["run"])].append(r)
        elif f.startswith("steps_"):
            for r in jl(os.path.join(run_dir, f)):
                steps[(r["id"], r["run"])] = r["steps"]
    out = []
    for lab in jl(os.path.join(run_dir, "labels.jsonl")):
        if not lab.get("turn_end") or lab.get("done") is None:
            continue
        key = (lab["id"], lab["run"])
        r, log = states[key][lab["k"]], steps.get(key)
        if log is None:
            continue
        calls = [s for s in log if s["turn"] == r["turn"] and s["kind"] == "call"]
        out.append({"uid": f"{lab['id']}|{lab['run']}|{lab['k']}|turn", "split": split, "scenario": lab["scenario"],
                    "version": lab["version"], "turn": lab["turn"], "label": int(lab["done"]),
                    "text": state_text(r["requests"], calls, r["step"]["text"])})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir"); ap.add_argument("train_dir"); ap.add_argument("val_dir")
    ap.add_argument("--dev-scenarios", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    tr, va = rows(a.train_dir, "train"), rows(a.val_dir, "val")
    scen = sorted({r["scenario"] for r in tr})
    dev = set(random.Random(0).sample(scen, a.dev_scenarios))
    for r in tr:
        if r["scenario"] in dev:
            r["split"] = "dev"
    for name in ("train", "dev", "val"):
        rs = [r for r in tr + va if r["split"] == name]
        with open(os.path.join(a.out_dir, f"{name}.jsonl"), "w") as f:
            for r in rs:
                f.write(json.dumps(r) + "\n")
        nd = sum(1 - r["label"] for r in rs)
        print(f"{name}: {len(rs)} turn ends, not done {nd} ({100 * nd / max(len(rs), 1):.1f}%), "
              f"{len({r['scenario'] for r in rs})} scenarios, median chars {sorted(len(r['text']) for r in rs)[len(rs) // 2]}")


if __name__ == "__main__":
    main()
