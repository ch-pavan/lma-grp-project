# Finetuned Laya heads on every recorded step of an S1_record run (the test passes of item 4.1), for the offline F1.
# Inputs are built as in training: calls with build_step_data.state_text on the recorded state, closing messages with
# build_done_data.state_text (the turn's calls from the steps log). Heads load through laya_step_judge.Head (fp16 on 2080 Ti).
# Writes one row per step: id, run, k, kind, p (P(bad) for calls, P(not done) for closing messages).
# usage: python analysis/score_test_heads.py RUN_DIR OUT.jsonl   (env LAYA_DIR, LAYA_STEP_WEIGHTS, LAYA_DONE_WEIGHTS, LAYA_DTYPE)
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laya_step_judge as J  # noqa: E402
import train_laya_done as T  # noqa: E402
from build_done_data import state_text as done_text  # noqa: E402
from build_step_data import state_text as step_text  # noqa: E402


def main():
    run_dir, out = sys.argv[1], sys.argv[2]
    states, steps = defaultdict(list), {}
    for f in sorted(os.listdir(run_dir)):
        if f.startswith("states_"):
            for l in open(os.path.join(run_dir, f)):
                r = json.loads(l)
                states[(r["id"], r["run"])].append(r)
        elif f.startswith("steps_"):
            for l in open(os.path.join(run_dir, f)):
                r = json.loads(l)
                steps[(r["id"], r["run"])] = r["steps"]
    items = []
    for (i, run), rs in states.items():
        for k, r in enumerate(rs):
            if r["step"]["kind"] == "call":
                items.append((i, run, k, "call", step_text(r)))
            else:
                calls = [s for s in steps.get((i, run), []) if s["turn"] == r["turn"] and s["kind"] == "call"]
                items.append((i, run, k, "msg", done_text(r["requests"], calls, r["step"]["text"])))
    e, dt = os.environ, os.environ.get("LAYA_DTYPE", "bf16")
    with open(out, "w") as f:
        for kind, w, q in (("call", e["LAYA_STEP_WEIGHTS"], T.STEP_QUESTION), ("msg", e["LAYA_DONE_WEIGHTS"], T.QUESTION)):
            head = J.Head(e["LAYA_DIR"], w, q, e.get("LAYA_DEVICE", "cuda:0"), dt)
            n = 0
            for i, run, k, kd, text in items:
                if kd == kind:
                    f.write(json.dumps({"id": i, "run": run, "k": k, "kind": kd, "p": round(head.p_bad(text), 5)}) + "\n")
                    n += 1
            print(f"{kind}: {n} steps scored", flush=True)
            del head


if __name__ == "__main__":
    main()
