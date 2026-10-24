# Step rankers for best of N: Skywork Reward V2 (pointwise scalar) and ToolPRM (pairwise "action_1"/"action_2"),
# plus an offline check on TRBench BFCL pairs and on our oracle labelled steps.
# usage: python rankers.py OUT_DIR TRB500.jsonl STATES.jsonl LABELS.jsonl MODEL [MODEL ...]
import hashlib, json, os, sys, time
import torch

try:  # GQA through SDPA falls back to the math kernel on Turing (full attention matrix); repeat KV heads instead
    import transformers.integrations.sdpa_attention as _SA
    _SA.use_gqa_in_sdpa = lambda *a, **k: False
except Exception:
    pass

TOOLPRM_TEMPLATE = (
    "Given the interaction history, function description and two actions, which "
    "action is the correct intermidiate step that could help in finishing the task:\n"
    "## history: {history}\n\n"
    "## function description: {functions}\n\n"
    "## action_1: {action_1}\n\n"
    "## action_2: {action_2}\n\n"
    "Please only generate action_1 or action_2 as the final answer.\n"
)
MAXTOK = int(os.environ.get("RANK_MAXTOK", 8192))


from rank_format import call_text, state_messages  # noqa: F401


class Skywork:
    kind = "scalar"

    def __init__(self, name, device="cuda:0", dtype=torch.float16):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(name)
        self.m = AutoModelForSequenceClassification.from_pretrained(name, torch_dtype=dtype, attn_implementation="sdpa", num_labels=1).to(device).eval()
        self.device = device

    @torch.no_grad()
    def score(self, msgs):
        ids = self.tok.apply_chat_template(msgs, tokenize=True, return_tensors="pt")
        ids = ids["input_ids"] if hasattr(ids, "keys") else ids
        if ids.shape[1] > MAXTOK:
            return None
        return float(self.m(ids.to(self.device)).logits[0][0].float())


class ToolPRM:
    kind = "pair"

    def __init__(self, name, device="cuda:0"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(name)
        self.m = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16, attn_implementation="sdpa").to(device).eval()
        self.device = device
        self.d1 = self.tok.encode("1", add_special_tokens=False)[-1]
        self.d2 = self.tok.encode("2", add_special_tokens=False)[-1]

    @torch.no_grad()
    def prefer_first(self, history_msgs, functions, a1, a2):
        """P(action_1 is better), from the digit after the first 'action_' the model writes (greedy)."""
        hist = "\n".join(f"{m['role']}: {m['content']}" for m in history_msgs)
        p = TOOLPRM_TEMPLATE.format(history=hist, functions=functions, action_1=a1, action_2=a2)
        kw = {"enable_thinking": False}
        ids = self.tok.apply_chat_template([{"role": "user", "content": p}], tokenize=True, add_generation_prompt=True, return_tensors="pt", **kw)
        ids = ids["input_ids"] if hasattr(ids, "keys") else ids
        if ids.shape[1] > MAXTOK:
            return None, ""
        out = self.m.generate(ids.to(self.device), max_new_tokens=48, do_sample=False, output_scores=True, return_dict_in_generate=True)
        gen = out.sequences[0, ids.shape[1]:].tolist()
        text = self.tok.decode(gen)
        for i, t in enumerate(gen):
            if t in (self.d1, self.d2) and "action" in self.tok.decode(gen[max(0, i - 3):i]):
                lp = torch.log_softmax(out.scores[i][0].float(), -1)
                return float(torch.sigmoid(lp[self.d1] - lp[self.d2])), text
        return (1.0 if "action_1" in text and "action_2" not in text else 0.0 if "action_2" in text else 0.5), text


def load(name):
    return ToolPRM(name) if "ToolPRM" in name else Skywork(name)


def auroc(y, s):
    pos = [b for a, b in zip(y, s) if a == 1]
    neg = [b for a, b in zip(y, s) if a == 0]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    out, trb_p, states_p, labels_p, models = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
    os.makedirs(out, exist_ok=True)
    trb = [json.loads(l) for l in open(trb_p)]  # pre sampled: 300 multi_turn_base + 200 other pairs, sha256 order
    key = lambda s: hashlib.sha256(str(s).encode()).hexdigest()
    import run as R
    # our steps: every oracle flag plus unflagged steps up to N_OURS, sha256 order
    lab = {(r["id"], r["run"], r["k"]): r["oracle"] for r in map(json.loads, open(labels_p))}
    seen, steps = {}, []
    for l in open(states_p):
        r = json.loads(l)
        k = (r["id"], r["run"]); r["k"] = seen.get(k, 0); seen[k] = r["k"] + 1
        y = lab.get((r["id"], r["run"], r["k"]))
        if y is not None:
            r["y"] = y; steps.append(r)
    steps.sort(key=lambda r: key((r["id"], r["run"], r["k"])))
    n_ours = int(os.environ.get("N_OURS", 800))
    pos = [r for r in steps if r["y"] == 1]
    steps = pos + [r for r in steps if r["y"] == 0][:max(n_ours - len(pos), 0)]
    E = {e["id"]: e for v in R.VERSIONS for e in R.load_version(v)}
    for name in models:
        t0 = time.time()
        try:
            m = load(name)
        except Exception as ex:
            print(f"LOAD_FAIL {name}: {type(ex).__name__} {str(ex)[:300]}", flush=True)
            continue
        tag = name.split("/")[-1]
        f = open(os.path.join(out, f"{tag}.jsonl"), "w")
        acc = {"mt": [], "other": []}
        for r in trb:
            r = type("Row", (), r)
            hist = list(r.chat_history)
            if m.kind == "scalar":
                sc, sr = m.score(hist + [{"role": "assistant", "content": r.chosen_response}]), m.score(hist + [{"role": "assistant", "content": r.reject_response}])
                if sc is None or sr is None:
                    continue
                ok = float(sc > sr)
                row = {"src": "trb", "task": r.task_source, "chosen": sc, "reject": sr}
            else:
                sysm = next((h["content"] for h in hist if h["role"] == "system"), "")
                rest = [h for h in hist if h["role"] != "system"]
                flip = int(key(r.uuid)[0], 16) % 2  # half the pairs put the chosen one second
                a1, a2 = (r.reject_response, r.chosen_response) if flip else (r.chosen_response, r.reject_response)
                p1, text = m.prefer_first(rest, sysm, a1, a2)
                if p1 is None:
                    continue
                ok = float((p1 < 0.5) if flip else (p1 > 0.5))
                row = {"src": "trb", "task": r.task_source, "p_first": p1, "flip": flip, "text": text[:80]}
            row["ok"] = ok
            if len(acc["mt"]) + len(acc["other"]) in (1, 10, 50, 200):
                print(f"  {tag} trb {len(acc['mt']) + len(acc['other'])} pairs {time.time()-t0:.0f}s", flush=True)
            acc["mt" if r.task_source == "multi_turn_base" else "other"].append(ok)
            f.write(json.dumps(row) + "\n")
        res = {"model": name, "trb_mt_acc": sum(acc["mt"]) / max(len(acc["mt"]), 1), "trb_mt_n": len(acc["mt"]),
               "trb_other_acc": sum(acc["other"]) / max(len(acc["other"]), 1), "trb_other_n": len(acc["other"])}
        if m.kind == "scalar":
            ys, ss, kinds = [], [], []
            for r in steps:
                e = E[r["id"]]
                docs = [d for c in e["involved_classes"] for d in R.docs_for(c)]
                st = r["step"]
                resp = call_text(st["name"], st.get("args") or {}) if st["kind"] == "call" else st["text"]
                s = m.score(state_messages(r["requests"], r["recent"], docs, resp))
                if s is None:
                    continue
                ys.append(r["y"]); ss.append(-s); kinds.append(st["kind"])
                f.write(json.dumps({"src": "ours", "id": r["id"], "run": r["run"], "k": r["k"], "kind": st["kind"], "y": r["y"], "score": s}) + "\n")
            res["ours_auroc"] = auroc(ys, ss)
            for kd in ("call", "msg"):
                res[f"ours_auroc_{kd}"] = auroc([y for y, k in zip(ys, kinds) if k == kd], [s for s, k in zip(ss, kinds) if k == kd])
            res["ours_n"], res["ours_pos"] = len(ys), sum(ys)
        res["seconds"] = time.time() - t0
        print("RANKER", json.dumps(res), flush=True)
        json.dump(res, open(os.path.join(out, f"{tag}.summary.json"), "w"))
        del m
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
