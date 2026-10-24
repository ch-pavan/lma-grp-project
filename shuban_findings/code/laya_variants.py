# Laya used without finetuning, in several ways: state formats, question wordings, thresholds and a small
# logistic head on its decision probabilities. Also a recorder that saves every judged state.
# Nothing here changes run.py; laya_run.py patches it at import time.
import asyncio, contextvars, json, math, os, threading
import prompts as P

CUR = contextvars.ContextVar("cur", default=None)


# ---------------- state formats ----------------
def ev_text(ev):
    return "; ".join(f"{k}={v!r}: {w}" for k, v, w in ev) if ev else "(no argument values)"


def step_line(s):
    return (f"PROPOSED TOOL CALL: {P.cut(s['text'], 400)}" if s["kind"] == "call"
            else f"PROPOSED CLOSING MESSAGE: {P.cut(s['text'], 600)}")


def calls_lines(recent, n=3, k=200):
    return [f"- {P.cut(c, k)} -> {P.cut(o, k)}" for c, o in recent[-n:]] or ["- (none)"]


def f_orig(r):
    return P.build_state(r["requests"], r["plan"], r["recent"], r["step"], r["step"]["ev"])


def f_step_first(r):
    # laya keeps the start of a string state, so the step it judges goes first
    s = r["step"]
    lines = [step_line(s), "EVIDENCE: " + ev_text(s["ev"]), "LATEST USER REQUEST: " + P.cut(r["requests"][-1], 600),
             "LAST CALLS:"] + calls_lines(r["recent"]) + ["TURN PLAN: " + P.cut(r["plan"] or "(none)", 400)]
    if len(r["requests"]) > 1:
        lines.append("EARLIER REQUESTS: " + " | ".join(P.cut(x, 200) for x in r["requests"][-4:-1]))
    return "\n".join(lines)


def f_compact(r):
    s = r["step"]
    lines = ["USER REQUEST: " + P.cut(r["requests"][-1], 500), "LAST CALLS:"] + calls_lines(r["recent"], 2, 150) + [step_line(s)]
    if s["kind"] == "call":
        lines.append("EVIDENCE: " + ev_text(s["ev"]))
    return "\n".join(lines)


def f_dict(r):
    s = r["step"]
    return {"proposed_step": P.cut(s["text"], 500), "step_kind": "tool call" if s["kind"] == "call" else "closing message",
            "latest_user_request": P.cut(r["requests"][-1], 500), "evidence": ev_text(s["ev"]),
            "last_calls": [f"{P.cut(c, 150)} -> {P.cut(o, 150)}" for c, o in r["recent"][-3:]], "plan": P.cut(r["plan"] or "", 300)}


FORMATS = {"orig": f_orig, "step_first": f_step_first, "compact": f_compact, "dict": f_dict}


# ---------------- questions ----------------
# each entry: kind -> qdef, and how to read P(flag) from laya's answer
def ch(ins, crit):
    return {"type": "choice", "instructions": ins, "criteria": crit}


def noul(ins):
    return {"type": "noul", "instructions": ins}


QUESTIONS = {
    "q1_orig": {"call": ch("Is the proposed step on track for the user's latest request?",
                           {"on_track": "plausibly advances the latest request, including reads that gather needed information and asking the user for a missing value",
                            "off_track": "wrong target, a state change nobody asked for, a goal swapped for a related one, stopping early, or acting when it should ask"}),
                "flag": ("off_track",)},
    "q2_orig": {"call": ch("Does the proposed tool call use a made up value?",
                           {"none": "every argument value comes from the requests, tool outputs or tool docs, or simple arithmetic on them",
                            "made_up_value": "an id, path, name or number that appears nowhere, or a withheld value filled in instead of asking"}),
                "msg": ch("Is the closing message to the user hallucinated?",
                          {"none": "everything it reports is shown by the tool outputs",
                           "made_up_value": "it states a value that appears nowhere",
                           "false_claim": "it reports a success or result the trace does not show"}),
                "flag": ("made_up_value", "false_claim")},
    "q1_swap": {"call": ch("Is the proposed step on track for the user's latest request?",
                           {"off_track": "wrong target, a state change nobody asked for, a goal swapped for a related one, stopping early, or acting when it should ask",
                            "on_track": "plausibly advances the latest request, including reads that gather needed information and asking the user for a missing value"}),
                "flag": ("off_track",)},
    "q_proceed": {"call": ch("Should the agent go ahead with the proposed step?",
                             {"proceed": "the step is a reasonable next move toward what the user asked",
                              "revise": "the step is clearly wrong for what the user asked"}),
                  "flag": ("revise",)},
    "q_3way": {"call": ch("What should happen to the proposed step?",
                          {"proceed": "it is a reasonable next move toward what the user asked",
                           "ask_user": "a value the step needs was never given, so the agent should ask the user",
                           "revise": "it is clearly wrong for what the user asked"}),
               "flag": ("revise",)},
    "q_wrong": {"call": noul("Is the proposed step clearly wrong for the user's latest request?"), "flag": ("true",)},
    "q_ok": {"call": noul("Is the proposed step a reasonable next action for the user's latest request?"), "flag": ("false",)},
    "q2_noul": {"call": noul("Does the proposed tool call use an argument value that appears nowhere in the requests, tool outputs or tool docs?"),
                "msg": noul("Does the closing message state a result or value that the tool outputs do not show?"),
                "flag": ("true",)},
}
for _q in QUESTIONS.values():  # same wording for closing messages unless a message version is given
    _q.setdefault("msg", _q["call"])


def p_flag(ans, flag):
    if "noul" in ans:
        p = float(ans["noul"])
        return p if flag == ("true",) else 1 - p
    return float(sum(ans["probabilities"].get(f, 0.0) for f in flag))


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def features(agent, recs, pairs, batch_size=16, max_len=None):
    """P(flag) for every (format, question) pair on every record: list of dicts keyed 'fmt|qid'."""
    out = [dict() for _ in recs]
    for fmt in sorted({f for f, _ in pairs}):
        qids = [q for f, q in pairs if f == fmt]
        for kind in ("call", "msg"):
            idx = [i for i, r in enumerate(recs) if r["step"]["kind"] == kind]
            if not idx:
                continue
            states = [FORMATS[fmt](recs[i]) for i in idx]
            qs = {q: QUESTIONS[q][kind] for q in qids}
            kw = {"batch_size": batch_size, "sort_by_length": len(states) > batch_size > 1}
            if max_len:
                kw["max_len"] = max_len
            res = agent.predict_batch(states, qs, **kw)
            for i, rr in zip(idx, res):
                for q in qids:
                    out[i][f"{fmt}|{q}"] = p_flag(rr["answers"][q], QUESTIONS[q]["flag"])
    return out


# ---------------- online judge ----------------
class LayaVariantJudge:
    """Flags a step when a logistic score over laya P(flag) features passes a threshold fit on non test steps.

    cfg: {"name", "call": part or null, "msg": part or null}; part: {"feats": ["fmt|qid", ...], "w": [...], "b": float, "t": float}.
    A step kind with no part is not judged. A flagged call is drift (q1), a flagged message a false claim (q2).
    """

    def __init__(self, cfg, device="cuda:0"):
        import laya
        self.cfg = cfg
        self.agent = laya.load("convaiinnovations/laya-typed-decisions", device=device)
        self.lock = threading.Lock()
        self.name = "S4v_" + cfg["name"]

    def score(self, rec, part):
        with self.lock:
            f = features(self.agent, [rec], [tuple(k.split("|")) for k in part["feats"]], batch_size=8)[0]
        return part["b"] + sum(w * logit(f[k]) for w, k in zip(part["w"], part["feats"]))

    async def judge(self, ctx, step):
        part = self.cfg.get(step["kind"])
        out = {"q1": "on_track", "q2": "none", "q3": "needed", "jin": 0, "jout": 0}
        if not part:
            return out
        rec = {"requests": ctx["requests"], "plan": ctx["plan"], "recent": ctx["recent"], "step": step}
        z = await asyncio.to_thread(self.score, rec, part)
        out["score"] = round(z, 3)
        if z > part["t"]:
            if step["kind"] == "call":
                out["q1"] = "off_track"
            else:
                out["q2"] = "false_claim"
        return out


# ---------------- recorder ----------------
class Recorder:
    """Saves the full judge input of every judged step, then defers to the wrapped judge."""

    def __init__(self, inner, path):
        self.inner, self.f, self.lock = inner, open(path, "a"), threading.Lock()
        self.name = getattr(inner, "name", "rec")

    async def judge(self, ctx, step):
        v = await self.inner.judge(ctx, step)
        cur = CUR.get() or {}
        t = len(ctx["requests"]) - 1
        gold = cur.get("gold")
        row = {"id": cur.get("id"), "run": cur.get("run"), "version": cur.get("version"), "scenario": cur.get("scenario"),
               "turn": t, "gold_turn": gold[t] if gold and t < len(gold) else None,
               "requests": ctx["requests"], "plan": ctx["plan"], "recent": [[c, str(o)[:1500]] for c, o in ctx["recent"][-4:]],
               "n_recent": len(ctx["recent"]), "step": {k: step[k] for k in ("kind", "name", "args", "text", "ev") if k in step},
               "verdict": {k: v.get(k) for k in ("q1", "q2", "score")}}
        with self.lock:
            self.f.write(json.dumps(row, default=str) + "\n"); self.f.flush()
        return v
