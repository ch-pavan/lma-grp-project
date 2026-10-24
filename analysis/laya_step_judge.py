# Finetuned Laya as step check plus done check inside Shuban's harness (actions.py, rollback modes such as rb2c).
# A proposed call is judged by the step head (P(bad) >= LAYA_STEP_THR -> off_track, so the call is rolled back and
# resampled); a closing message by the done head (P(not done) >= LAYA_DONE_THR -> false_claim), the same as S_layadone.
# Selected as system S_layastep; env LAYA_DIR, LAYA_STEP_WEIGHTS, LAYA_STEP_THR, LAYA_DONE_WEIGHTS, LAYA_DONE_THR.
import asyncio, os, sys, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch  # noqa: E402
import train_laya_done as T  # noqa: E402
from build_done_data import state_text as done_text  # noqa: E402
from build_step_data import state_text as step_text  # noqa: E402


class Head:
    def __init__(self, model_dir, weights, question, device):
        import laya
        self.agent = laya.load(model_dir, device=device)
        self.agent.model.load_state_dict(torch.load(weights, map_location="cpu"), strict=False)
        self.agent.model.eval()
        self.enc, self.device = T.Encoder(self.agent, question), device

    @torch.no_grad()
    def p_bad(self, text):
        b = T.collate([self.enc.item(text)], self.agent.tok.pad_token_id)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.device.startswith("cuda")):
            logits, _ = self.agent.model(*(b[k].to(self.device) for k in ("input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype")))
        return float(torch.softmax(logits.float()[0, :2], -1)[T.NOT_DONE])


class LayaStepJudge:
    name = "S_layastep"

    def __init__(self, model_dir, step_w, step_thr, done_w, done_thr, device="cuda:0"):
        self.step = Head(model_dir, step_w, T.STEP_QUESTION, device)
        self.done = Head(model_dir, done_w, T.QUESTION, device)
        self.step_thr, self.done_thr, self.lock = step_thr, done_thr, threading.Lock()

    def _p(self, head, text):
        with self.lock:
            return head.p_bad(text)

    async def judge(self, ctx, step):
        v = {"q1": "on_track", "q2": "none", "q3": "needed", "jin": 0, "jout": 0}
        if step["kind"] == "msg":
            calls = [{"call": c, "out": str(o)[:300]} for c, o in ctx.get("turn_calls", [])]
            p = await asyncio.to_thread(self._p, self.done, done_text(ctx["requests"], calls, step["text"]))
            return {**v, "q2": "false_claim" if p >= self.done_thr else "none", "p_not_done": round(p, 4)}
        st = {"requests": ctx["requests"], "plan": ctx.get("plan"), "recent": list(ctx.get("recent") or [])[-3:], "step": step}
        p = await asyncio.to_thread(self._p, self.step, step_text(st))
        return {**v, "q1": "off_track" if p >= self.step_thr else "on_track", "p_bad": round(p, 4)}


def make():
    e = os.environ
    return LayaStepJudge(e["LAYA_DIR"], e["LAYA_STEP_WEIGHTS"], float(e["LAYA_STEP_THR"]), e["LAYA_DONE_WEIGHTS"],
                         float(e.get("LAYA_DONE_THR", "0.5")), e.get("LAYA_DEVICE", "cuda:0"))
