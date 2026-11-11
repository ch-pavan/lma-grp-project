# Plan item 4.4 (analysis/2026-11-09_typed_closing_head.md): finetune Laya typed decisions on closing messages with one
# three-option choice question (done / off_track / false_claim), from analysis/build_typed_data.py rows. The recipe is the
# frozen done head's (train_laya_done.py: full finetune, 2 epochs, batch 32, lr 2e-5 / 1e-4, max length 1,024, option
# order shuffled, balanced class weights), with the two annotators' labels averaged into a soft target. The last epoch is
# kept. No threshold is chosen here.
#   --fold K : train on the other folds of train.jsonl, write P(class) for fold K to scores.jsonl (out of fold)
#   --fold -1: train on all of train.jsonl, write P(class) for val.jsonl to scores.jsonl and the weights to weights.pt
#   --check  : only score Laya as is with the done question on the done head's dev rows (environment check against the
#              Ada logs, AUROC 0.752), then exit
# usage: python analysis/train_laya_typed.py DATA_DIR MODEL_DIR OUT_DIR [--fold K] [--seed S] [--check]
import argparse, json, math, os, random, sys, time

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_laya_done as T  # noqa: E402

TYPED = {
    "type": "choice",
    "instructions": "When the agent ended its turn, did it finish the user's latest request, and does its closing "
                    "message match what the tool calls show?",
    "criteria": {
        "done": "every part of the latest request was carried out or answered from tool outputs, "
                "or the agent rightly asked the user for a missing value",
        "off_track": "some part of the request was not carried out, or a change used a value only the user could give",
        "false_claim": "the closing message reports a success or result that the tool calls and outputs do not show",
    },
}
K = 3


@torch.no_grad()
def score(model, enc, rows, device, bs, dtype):
    """P(done), P(off_track), P(false_claim) per row, option order fixed."""
    model.eval()
    items = [enc.item(r["text"]) for r in rows]
    out = np.zeros((len(rows), K))
    for ch in T.batches(items, bs, False, 0):
        b = T.collate([items[i] for i in ch], enc.agent.tok.pad_token_id)
        with torch.autocast("cuda", dtype=dtype, enabled=device.startswith("cuda")):
            logits, _ = model(b["input_ids"].to(device), b["attention_mask"].to(device), b["marker_pos"].to(device),
                              b["marker_mask"].to(device), b["qtype"].to(device))
        out[ch] = torch.softmax(logits.float()[:, :K], -1).cpu().numpy()
    return out


def soft(r):
    ys = [c for c in r["y"] if c is not None]
    t = np.zeros(K)
    for c in ys:
        t[c] += 1 / len(ys)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir"); ap.add_argument("model_dir"); ap.add_argument("out_dir")
    ap.add_argument("--fold", type=int, default=-1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--lr-head", type=float, default=1e-4)
    ap.add_argument("--lr-enc", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp16"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    import laya
    t0 = time.time()
    agent = laya.load(a.model_dir, device=a.device)
    agent.cfg["max_len"] = a.max_len
    model = agent.model
    dtype = torch.bfloat16 if a.dtype == "bf16" else torch.float16
    print(f"laya {laya.__version__}, torch {torch.__version__}, loaded in {time.time() - t0:.0f}s", flush=True)

    if a.check:
        dev = T.jl("runs/data/laya_done/dev.jsonl")
        s = T.score(model, T.Encoder(agent, T.QUESTION), dev, a.device, 64, dtype)
        y = [1 - r["label"] for r in dev]
        print(f"CHECK Laya as is, done question, dev: AUROC {T.auroc(y, s):.4f} on {len(dev)} rows (Ada logs: 0.7524)", flush=True)
        return

    enc = T.Encoder(agent, TYPED)
    rows = T.jl(os.path.join(a.data_dir, "train.jsonl"))
    if a.fold >= 0:
        train = [r for r in rows if r["fold"] != a.fold]; held = [r for r in rows if r["fold"] == a.fold]
    else:
        train, held = rows, T.jl(os.path.join(a.data_dir, "val.jsonl"))
    tgt_all = np.stack([soft(r) for r in train])
    cnt = tgt_all.sum(0)
    w = torch.tensor(len(train) / (K * np.maximum(cnt, 1e-6)), dtype=torch.float32, device=a.device)
    print(f"fold {a.fold}, seed {a.seed}: train {len(train)} rows, class mass {np.round(cnt, 1).tolist()}, "
          f"weights {[round(x, 2) for x in w.tolist()]}; scored {len(held)}", flush=True)

    model.requires_grad_(True)
    model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    groups = [{"params": [p for n, p in model.named_parameters() if n.startswith("encoder.")], "lr": a.lr_enc},
              {"params": [p for n, p in model.named_parameters() if not n.startswith("encoder.")], "lr": a.lr_head}]
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=a.dtype == "fp16" and a.device.startswith("cuda"))
    steps = a.epochs * math.ceil(len(train) / a.bs); warm = max(1, steps // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda k: min(1.0, (k + 1) / warm) * max(0.0, (steps - k) / max(1, steps - warm)))
    rng = random.Random(a.seed)
    log = []
    for ep in range(a.epochs):
        model.train()
        items, tgts = [], []
        for r, t in zip(train, tgt_all):
            order = list(range(K)); rng.shuffle(order)  # order[slot] = class shown in that slot
            items.append(enc.item(r["text"], order)); tgts.append(t[order])
        te, tl, nb = time.time(), 0.0, 0
        for ch in T.batches(items, a.bs, True, a.seed + ep):
            opt.zero_grad(set_to_none=True)
            step_loss, mb = 0.0, math.ceil(len(ch) / a.accum)
            for k in range(0, len(ch), mb):
                sub = ch[k:k + mb]
                b = T.collate([items[i] for i in sub], agent.tok.pad_token_id)
                t_slot = torch.tensor(np.stack([tgts[i] for i in sub]), dtype=torch.float32, device=a.device)
                t_cls = torch.tensor(np.stack([tgt_all[i] for i in sub]), dtype=torch.float32, device=a.device)
                with torch.autocast("cuda", dtype=dtype, enabled=a.device.startswith("cuda")):
                    logits, _ = model(b["input_ids"].to(a.device), b["attention_mask"].to(a.device), b["marker_pos"].to(a.device),
                                      b["marker_mask"].to(a.device), b["qtype"].to(a.device))
                ce = -(t_slot * F.log_softmax(logits.float()[:, :K], -1)).sum(-1)
                loss = (ce * (t_cls * w).sum(-1)).sum() / len(ch)
                scaler.scale(loss).backward(); step_loss += loss.item()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_([p for g in groups for p in g["params"]], 1.0)
            scaler.step(opt); scaler.update(); sched.step(); tl += step_loss; nb += 1
        print(f"epoch {ep + 1}: loss {tl / nb:.4f}, {time.time() - te:.0f}s", flush=True)
        log.append({"epoch": ep + 1, "loss": tl / nb, "seconds": time.time() - te})
    s = score(model, enc, held, a.device, 64, dtype)
    with open(os.path.join(a.out_dir, "scores.jsonl"), "w") as f:
        for r, p in zip(held, s):
            f.write(json.dumps({"uid": r["uid"], "y": r["y"], "p": [round(float(x), 5) for x in p]}) + "\n")
    json.dump({"args": vars(a), "epochs": log, "class_mass": cnt.tolist()}, open(os.path.join(a.out_dir, "results.json"), "w"), indent=1)
    if a.fold < 0:
        torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, os.path.join(a.out_dir, "weights.pt"))
    print(f"DONE in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
