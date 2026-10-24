# Finetuned Laya as the turn end done check inside Shuban's harness (actions.py, mode dc).
# The harness calls judge() on the closing message; P(not done) >= threshold means not done (q2 false_claim),
# so the closing message is dropped and the agent is told the request may be unfinished.
# Selected as system S_layadone; env LAYA_DIR (base checkpoint), LAYA_DONE_WEIGHTS (state dict), LAYA_DONE_THR.
import asyncio, os, sys, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch  # noqa: E402
import train_laya_done as T  # noqa: E402
from build_done_data import state_text  # noqa: E402


class LayaDoneJudge:
    name = "S_layadone"

    def __init__(self, model_dir, weights, device="cuda:0", thr=0.5):
        import laya
        self.agent = laya.load(model_dir, device=device)
        self.agent.model.load_state_dict(torch.load(weights, map_location="cpu"), strict=False)
        self.agent.model.eval()
        self.enc, self.thr, self.device, self.lock = T.Encoder(self.agent), thr, device, threading.Lock()

    @torch.no_grad()
    def p_not_done(self, text):
        with self.lock:
            b = T.collate([self.enc.item(text)], self.agent.tok.pad_token_id)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.device.startswith("cuda")):
                logits, _ = self.agent.model(*(b[k].to(self.device) for k in ("input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype")))
            return float(torch.softmax(logits.float()[0, :2], -1)[T.NOT_DONE])

    async def judge(self, ctx, step):
        v = {"q1": "on_track", "q2": "none", "q3": "needed", "jin": 0, "jout": 0}
        if step["kind"] != "msg":
            return v
        calls = [{"call": c, "out": str(o)[:300]} for c, o in ctx.get("turn_calls", [])]
        p = await asyncio.to_thread(self.p_not_done, state_text(ctx["requests"], calls, step["text"]))
        return {**v, "q2": "false_claim" if p >= self.thr else "none", "p_not_done": round(p, 4)}


def make():
    return LayaDoneJudge(os.environ["LAYA_DIR"], os.environ["LAYA_DONE_WEIGHTS"], os.environ.get("LAYA_DEVICE", "cuda:0"),
                         float(os.environ.get("LAYA_DONE_THR", "0.5")))
