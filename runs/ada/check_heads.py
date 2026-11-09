# Check that the Laya heads score as in training when loaded through analysis/laya_step_judge.py in the test run's
# environment (vLLM pins, laya 0.3.27, fp16): AUROC and flag rate on the validation sets they were scored on in training.
# Also prints the step judge's input text for a few recorded steps of a test run, to compare with the training text.
# usage: python check_heads.py <step weights> <done weights> <laya_step/val.jsonl> <laya_done/val.jsonl> [states.jsonl]
import json, os, sys
sys.path.insert(0, os.environ.get("STAY_ANALYSIS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "analysis")))
import laya_step_judge as J  # noqa: E402
import train_laya_done as T  # noqa: E402
from build_step_data import state_text as step_text  # noqa: E402


def auroc(y, s):
    pos = [x for x, t in zip(s, y) if t]; neg = [x for x, t in zip(s, y) if not t]
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))


def score(head, path, n=100000):
    rows = [json.loads(l) for l in open(path)][:n]
    s = [head.p_bad(r["text"]) for r in rows]
    y = [r["label"] in ("0", 0) for r in rows]  # label 1 = ok / done
    return y, s


def _p32(h, text):
    import torch
    b = T.collate([h.enc.item(text)], h.agent.tok.pad_token_id)
    with torch.no_grad():
        logits, _ = h.agent.model(*(b[k].to(h.device) for k in ("input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype")))
    return float(torch.softmax(logits.float()[0, :2], -1)[T.NOT_DONE])


sw, dw, sv, dv = sys.argv[1:5]
for dtype in ("fp16", "fp32"):
    for name, w, q, v, thr in (("step", sw, T.STEP_QUESTION, sv, 0.1266), ("done", dw, T.QUESTION, dv, 0.561)):
        h = J.Head(os.environ["LAYA_DIR"], w, q, "cuda:0", "fp16" if dtype == "fp16" else "bf16")
        if dtype == "fp32":
            h.agent.model.float()
            h.p_bad = (lambda hh: (lambda text: _p32(hh, text)))(h)
        y, s = score(h, v)
        print(f"{dtype} {name}: n {len(y)}, bad {sum(y)}, AUROC {auroc(y, s):.3f}, flagged at {thr} {sum(x >= thr for x in s) / len(s):.1%}, "
              f"mean score {sum(s) / len(s):.3f}", flush=True)
        del h



if len(sys.argv) > 5:
    for l in list(open(sys.argv[5]))[:3]:
        r = json.loads(l)
        if r["step"]["kind"] == "call":
            st = {"requests": r["requests"], "plan": r["plan"], "recent": r["recent"][-3:], "step": r["step"]}
            print("----\n" + step_text(st)[:1200])
