# Runs on the GPU. Scores the labelled test steps (sample_order.txt) with Laya's heads, for the final comparison:
#   frozen step head (orig_seed1)  on tool calls       -> P(bad)
#   frozen done head (64348)       on closing messages -> P(not done)
#   typed head of item 4.4 (run chosen on validation)  on closing messages -> P(done), P(off track), P(false claim)
# Inputs are built exactly as for training and validation (build_step_data.state_text, build_done_data.rows). Every head
# is first run on validation and compared with the scores saved when it was trained (--verify), so a wrong load or a
# different software stack shows up before any test number exists. fp32, no autocast.
# usage: python analysis/score_test.py TEST_RUN_DIR SAMPLE_ORDER MODEL_DIR STEP_PT DONE_PT TYPED_PT OUT.jsonl
import argparse, gzip, json, os, sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shuban_findings", "code"))
import train_laya_done as T  # noqa: E402
import train_laya_typed as TT  # noqa: E402
import build_step_data as BS  # noqa: E402
import build_done_data as BD  # noqa: E402
import offline_eval as E  # noqa: E402


def jl(p):
    with (gzip.open(p, "rt") if p.endswith(".gz") else open(p)) as f:
        return [json.loads(l) for l in f if l.strip()]


@torch.no_grad()
def probs(agent, question, texts, n):
    enc = T.Encoder(agent, question); model = agent.model; model.eval()
    items = [enc.item(t) for t in texts]
    out = np.zeros((len(texts), n))
    for ch in T.batches(items, 64, False, 0):
        b = T.collate([items[i] for i in ch], agent.tok.pad_token_id)
        logits, _ = model(b["input_ids"].cuda(), b["attention_mask"].cuda(), b["marker_pos"].cuda(), b["marker_mask"].cuda(),
                          b["qtype"].cuda())
        out[ch] = torch.softmax(logits.float()[:, :n], -1).cpu().numpy()
    return out


def load_head(agent, path):
    sd = torch.load(path, map_location="cpu")
    missing, unexpected = agent.model.load_state_dict(sd, strict=False)
    print(f"loaded {os.path.basename(path)}: {len(sd)} tensors, {len(missing)} missing, {len(unexpected)} unexpected", flush=True)


def verify(name, got, saved):
    d = np.abs(np.asarray(got) - np.asarray(saved))
    print(f"VERIFY {name}: {len(d)} val rows, mean |diff| {d.mean():.5f}, max {d.max():.4f}", flush=True)
    return d.max()


def main():
    ap = argparse.ArgumentParser()
    for x in ("test_dir", "sample", "model_dir", "step_pt", "done_pt", "typed_pt", "out"):
        ap.add_argument(x)
    ap.add_argument("--typed-val-scores", required=True, help="scores.jsonl of the chosen typed run on validation")
    ap.add_argument("--max-len", type=int, default=1024)
    a = ap.parse_args()
    import laya
    agent = laya.load(a.model_dir, device="cuda"); agent.cfg["max_len"] = a.max_len
    print(f"laya {laya.__version__}, torch {torch.__version__}", flush=True)

    want = [l.strip().split("|") for l in open(a.sample) if l.strip()]
    keys = [((i, int(r), int(k)), kind) for i, r, k, kind in want]
    rows = {(r["id"], r["run"], r["k"]): r for r in E.load_steps([a.test_dir])}
    msgs = {E.uid_key(r["uid"])[0]: r["text"] for r in BD.rows(a.test_dir, "test")}
    calls = [k for k, kind in keys if kind == "call"]; turns = [k for k, kind in keys if kind == "turn"]
    miss = [k for k in turns if k not in msgs]
    print(f"sample: {len(calls)} calls, {len(turns)} closing messages ({len(miss)} without a closing-message text)", flush=True)
    assert all(rows[k]["step"]["kind"] == "call" for k in calls)
    call_text = [BS.state_text(rows[k]) for k in calls]
    msg_keys = [k for k in turns if k in msgs]; msg_text = [msgs[k] for k in msg_keys]

    vs = [r for r in jl("runs/data/laya_step/val.jsonl") if r["source"] == "q35_9b:val"]
    vd = jl("runs/data/laya_done/val.jsonl")
    out = {}
    load_head(agent, a.step_pt)
    saved = {r["uid"]: r["p_not_done"] for r in jl("runs/data/laya_runs/ada_step_nobt/orig_seed1/val_scores.jsonl.gz")}
    m1 = verify("step head", probs(agent, T.STEP_QUESTION, [r["text"] for r in vs], 2)[:, 1], [saved[r["uid"]] for r in vs])
    for k, p in zip(calls, probs(agent, T.STEP_QUESTION, call_text, 2)[:, 1]):
        out[k] = {"kind": "call", "p_bad": round(float(p), 5)}
    load_head(agent, a.done_pt)
    saved = {r["uid"]: r["p_not_done"] for r in jl("runs/data/laya_runs/ada_done_full/val_scores.jsonl")}
    m2 = verify("done head", probs(agent, T.QUESTION, [r["text"] for r in vd], 2)[:, 1], [saved[r["uid"]] for r in vd])
    for k, p in zip(msg_keys, probs(agent, T.QUESTION, msg_text, 2)[:, 1]):
        out[k] = {"kind": "turn", "p_not_done": round(float(p), 5)}
    load_head(agent, a.typed_pt)
    saved = {r["uid"]: r["p"] for r in jl(a.typed_val_scores)}
    pv = probs(agent, TT.TYPED, [r["text"] for r in vd], 3)
    m3 = verify("typed head", pv.ravel(), np.concatenate([saved[r["uid"]] for r in vd]))
    for k, p in zip(msg_keys, probs(agent, TT.TYPED, msg_text, 3)):
        out[k]["p_typed"] = [round(float(x), 5) for x in p]
    with open(a.out, "w") as f:
        for (i, r, k), v in out.items():
            f.write(json.dumps({"id": i, "run": r, "k": k, **v}) + "\n")
    print(f"SCORED {len(out)} test steps; max val diff step {m1:.4f} done {m2:.4f} typed {m3:.4f}", flush=True)


if __name__ == "__main__":
    main()
