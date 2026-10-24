# Finetune Laya typed decisions on the turn end done check: one choice question, options done / not_done.
# mode head: encoder frozen, only the decision head trains. mode full: everything trains (lower lr on the encoder).
# Epoch picked on dev AUROC, threshold on dev F1 for not_done; val is only reported. Laya as is is scored first.
# usage: python train_laya_done.py DATA_DIR MODEL_DIR OUT_DIR [--mode head|full] [--epochs N] [--device cuda]
import argparse, json, math, os, random, sys, time

import numpy as np
import torch
import torch.nn.functional as F

QUESTION = {
    "type": "choice",
    "instructions": "Did the agent finish every part of the user's latest request before ending its turn?",
    "criteria": {
        "done": "every part of the latest request was carried out or answered from tool outputs, "
                "or the agent rightly asked the user for a missing value",
        "not_done": "some part of the request was not carried out, a value was guessed instead of asked, "
                    "or the closing message claims something the calls do not show",
    },
}
DONE, NOT_DONE = 0, 1


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def auroc(y, s):
    """y = 1 for the positive class (not done), s = score; ties counted half."""
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order)); allv = np.concatenate([pos, neg])[order]
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def prf(y, pred):
    tp = sum(1 for a, b in zip(y, pred) if a and b); fp = sum(1 for a, b in zip(y, pred) if not a and b)
    fn = sum(1 for a, b in zip(y, pred) if a and not b)
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def best_threshold(y, s):
    best = (0.0, 0.5)
    for t in sorted(set(np.round(s, 4))):
        f = prf(y, [x >= t for x in s])[2]
        if f > best[0]:
            best = (f, float(t))
    return best[1]


class Encoder:
    """Tokenizes states with Laya's own sequence builder; option order can be shuffled per example."""

    def __init__(self, agent):
        self.agent = agent
        self.q = agent._to_internal(QUESTION)

    def item(self, text, order=None):
        q = dict(self.q)
        if order is not None:
            q["option_order"] = order
        it = self.agent._encode_state(text, ["q"], {"q": q})[0]
        return it


def batches(items, bs, shuffle, seed):
    idx = sorted(range(len(items)), key=lambda i: len(items[i]["ids"]))  # length buckets: little padding
    chunks = [idx[i:i + bs] for i in range(0, len(idx), bs)]
    if shuffle:
        random.Random(seed).shuffle(chunks)
    return chunks


def collate(items, pad_id):
    from laya.common import collate_items
    return collate_items([[it] for it in items], pad_id)


@torch.no_grad()
def score(model, enc, rows, device, bs, dtype):
    """P(not_done) per row, option order fixed (done, not_done)."""
    model.eval()
    items = [enc.item(r["text"]) for r in rows]
    out = np.zeros(len(rows))
    for ch in batches(items, bs, False, 0):
        b = collate([items[i] for i in ch], enc.agent.tok.pad_token_id)
        with torch.autocast(device.split(":")[0], dtype=dtype, enabled=device.startswith("cuda")):
            logits, _ = model(b["input_ids"].to(device), b["attention_mask"].to(device), b["marker_pos"].to(device),
                              b["marker_mask"].to(device), b["qtype"].to(device))
        p = torch.softmax(logits.float()[:, :2], -1)[:, NOT_DONE].cpu().numpy()
        out[ch] = p
    return out


def report(name, rows, s, thr):
    y = [1 - r["label"] for r in rows]  # positive class = not done
    p, rc, f = prf(y, [x >= thr for x in s])
    acc = np.mean([(x >= thr) == bool(t) for x, t in zip(s, y)])
    res = {"auroc": round(auroc(y, s), 4), "f1_not_done": round(f, 4), "precision": round(p, 4), "recall": round(rc, 4),
           "accuracy": round(float(acc), 4), "threshold": round(thr, 4), "n": len(rows), "n_not_done": int(sum(y))}
    print(f"  {name:28s} AUROC {res['auroc']:.3f}  F1 {f:.3f}  P {p:.3f}  R {rc:.3f}  acc {acc:.3f}  thr {thr:.3f}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir"); ap.add_argument("model_dir"); ap.add_argument("out_dir")
    ap.add_argument("--mode", default="head", choices=["head", "full"])
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--accum", type=int, default=1, help="split each batch into this many micro batches (memory)")
    ap.add_argument("--grad-ckpt", type=int, default=1, help="gradient checkpointing in full mode")
    ap.add_argument("--lr-head", type=float, default=1e-4)
    ap.add_argument("--lr-enc", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="rows per split, for a smoke test")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    import laya
    t0 = time.time()
    agent = laya.load(a.model_dir, device=a.device)
    agent.cfg["max_len"] = a.max_len
    model, enc = agent.model, Encoder(agent)
    dtype = torch.bfloat16
    data = {s: jl(os.path.join(a.data_dir, f"{s}.jsonl")) for s in ("train", "dev", "val")}
    if a.limit:
        data = {s: random.Random(a.seed).sample(r, min(a.limit, len(r))) for s, r in data.items()}  # mixed labels
    print(f"loaded in {time.time() - t0:.0f}s; " + ", ".join(f"{s} {len(r)}" for s, r in data.items()) +
          f"; mode {a.mode}; laya {laya.__version__}", flush=True)
    trunc = sum(enc.item(r["text"])["state_stats"]["truncated"] for r in data["train"])
    print(f"states cut at max_len {a.max_len}: {trunc} of {len(data['train'])} train rows", flush=True)

    results = {"args": vars(a), "as_is": {}, "epochs": [], "best": {}}
    print("Laya as is (no training):", flush=True)
    s_dev, s_val = score(model, enc, data["dev"], a.device, 64, dtype), score(model, enc, data["val"], a.device, 64, dtype)
    thr = best_threshold([1 - r["label"] for r in data["dev"]], s_dev)
    results["as_is"] = {"dev": report("dev", data["dev"], s_dev, thr), "val": report("val (dev threshold)", data["val"], s_val, thr)}

    model.requires_grad_(True)
    if a.mode == "full" and a.grad_ckpt:
        model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.head_checkpointing = True
    if a.mode == "head":
        model.encoder.requires_grad_(False)
        groups = [{"params": [p for n, p in model.named_parameters() if not n.startswith("encoder.") and p.requires_grad],
                   "lr": a.lr_head}]
    else:
        groups = [{"params": [p for n, p in model.named_parameters() if n.startswith("encoder.")], "lr": a.lr_enc},
                  {"params": [p for n, p in model.named_parameters() if not n.startswith("encoder.")], "lr": a.lr_head}]
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    n = len(data["train"]); n_nd = min(max(1, sum(1 - r["label"] for r in data["train"])), n - 1)
    w = torch.tensor([n / (2 * (n - n_nd)), n / (2 * n_nd)], device=a.device)  # balanced: index 0 done, 1 not_done
    steps = a.epochs * math.ceil(n / a.bs); warm = max(1, steps // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda k: min(1.0, (k + 1) / warm) * max(0.0, (steps - k) / max(1, steps - warm)))
    rng = random.Random(a.seed)
    best_auc, best_state = -1.0, None
    for ep in range(a.epochs):
        model.train()
        if a.mode == "head":
            model.encoder.eval()  # frozen encoder: no dropout
        items, tgt = [], []
        for r in data["train"]:
            order = [0, 1] if rng.random() < 0.5 else [1, 0]
            lab = DONE if r["label"] else NOT_DONE
            items.append(enc.item(r["text"], order)); tgt.append((order.index(lab), lab))
        te, tl, nb = time.time(), 0.0, 0
        for ch in batches(items, a.bs, True, a.seed + ep):
            opt.zero_grad(set_to_none=True)
            step_loss, mb = 0.0, math.ceil(len(ch) / a.accum)
            for k in range(0, len(ch), mb):  # micro batches: same optimizer step as one batch of len(ch)
                sub = ch[k:k + mb]
                b = collate([items[i] for i in sub], agent.tok.pad_token_id)
                slot = torch.tensor([tgt[i][0] for i in sub], device=a.device)
                cls = torch.tensor([tgt[i][1] for i in sub], device=a.device)
                with torch.autocast("cuda", dtype=dtype, enabled=a.device.startswith("cuda")):
                    logits, _ = model(b["input_ids"].to(a.device), b["attention_mask"].to(a.device), b["marker_pos"].to(a.device),
                                      b["marker_mask"].to(a.device), b["qtype"].to(a.device), detach_encoder=a.mode == "head")
                loss = (F.cross_entropy(logits.float()[:, :2], slot, reduction="none") * w[cls]).sum() / len(ch)
                loss.backward(); step_loss += loss.item()
            torch.nn.utils.clip_grad_norm_([p for g in groups for p in g["params"]], 1.0)
            opt.step(); sched.step(); tl += step_loss; nb += 1
        s_dev = score(model, enc, data["dev"], a.device, 64, dtype)
        auc = auroc([1 - r["label"] for r in data["dev"]], s_dev)
        print(f"epoch {ep + 1}: loss {tl / nb:.4f}, dev AUROC {auc:.3f}, {time.time() - te:.0f}s", flush=True)
        results["epochs"].append({"epoch": ep + 1, "loss": tl / nb, "dev_auroc": auc, "seconds": time.time() - te})
        if auc > best_auc:
            best_auc = auc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                          if a.mode == "full" or not k.startswith("encoder.")}
            results["best"]["epoch"] = ep + 1
    model.load_state_dict(best_state, strict=False)
    print(f"Finetuned ({a.mode}, best epoch {results['best']['epoch']} by dev AUROC):", flush=True)
    s_dev, s_val = score(model, enc, data["dev"], a.device, 64, dtype), score(model, enc, data["val"], a.device, 64, dtype)
    thr = best_threshold([1 - r["label"] for r in data["dev"]], s_dev)
    results["best"].update(dev=report("dev", data["dev"], s_dev, thr), val=report("val (dev threshold)", data["val"], s_val, thr))
    with open(os.path.join(a.out_dir, "val_scores.jsonl"), "w") as f:
        for r, s in zip(data["val"], s_val):
            f.write(json.dumps({"uid": r["uid"], "label": r["label"], "p_not_done": round(float(s), 5)}) + "\n")
    json.dump(results, open(os.path.join(a.out_dir, "results.json"), "w"), indent=1)
    torch.save(best_state, os.path.join(a.out_dir, "weights.pt"))
    print(f"DONE in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
