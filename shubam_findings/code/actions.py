# Correction actions v2: what the harness does after a judge flag. A system is "<judge>@<mode>":
#   rb<K>     rollback: a flagged step never enters the doer's context; the doer resamples from the same state, up to K times
#   rbh<K>    rollback, and each resample gets one generic hint line (the rejected attempt is still never shown)
#   vote<N>   draw N steps at once; if all N agree run it unjudged, else judge them in vote order and run the first that passes
#   rank<N>   draw N steps at once; if they disagree a reward model (rank_server.py, RANKER_URL) scores them and the best runs
#   dc        done check only: no step judging; when the doer closes a turn the judge asks whether the request is done
#             (oracle: state equals the turn's reference end state and every reference function was called this turn)
#   suffix c  done check added to any mode (max 2 per turn; not done -> the closing message is dropped plus one neutral line)
#   suffix d  deep: a flagged closing message also drops the turn's trailing failed calls from the context before resampling
# When every candidate at a state is flagged, the one the judge was least sure about runs. A flag costs resamples, never a stall.
# Systems without "@" run the unchanged episode from run.py / agentdojo_run.py.
# usage: python actions.py --bench bfcl|agentdojo --system S3_llm_judge@rbh2 <run.py args> [--judge-url U --judge-model M]
import argparse, asyncio, bisect, contextvars, json, math, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as R
import laya_run  # noqa: F401  patches R.episode (sets laya_variants.CUR) and R.make_judge (S1_record, S_oracle)
import laya_variants as LV
import prompts as P

_strip_think = R.strip_think


def strip_think(s):
    """Qwen3.5 puts the opening <think> in the prompt, so its output carries only a closing tag."""
    s = s or ""
    if "</think>" in s and "<think>" not in s:
        s = s.split("</think>")[-1]
    return _strip_think(s)


R.strip_think = strip_think  # run.py and agentdojo_run.py judges and doers look it up here; Qwen3 output is unchanged

HINT = ("Before your next step, re check the user's latest request and use only values that appear in it, "
        "in earlier tool outputs or in the tool docs.")
MODE_RE = re.compile(r"^(rbh|rb|vote|rank|dc)(\d*)(d?)(c?)$")
RANKER_URL = os.environ.get("RANKER_URL", "http://127.0.0.1:8010/score")
LP = contextvars.ContextVar("lp", default=None)
UNFINISHED = "Part of the request may be unfinished. Check it, and continue if something is left."
DONE_GUIDE = """You check whether a tool using agent finished the user's latest request before it replies to the user. You get the user requests (latest last), the calls the agent made for the latest request with their outputs, and its closing message.
Decide whether every part of the latest request has been carried out by those calls, or answered from tool outputs. If a needed value was missing and the agent asks the user for it, or no tool can do the job and the agent says so, that counts as done.
Think briefly, then end with exactly one line: DONE=yes or DONE=no"""
DONE_RE = re.compile(r"DONE\s*=\s*(yes|no)", re.I)
CTX_ERR = "maximum context length"


def trim_old_outputs(messages, keep):
    """Older tool outputs cut to 300 chars, the last `keep` kept whole; used only when the server says the context is too long."""
    idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    old = set(idx[:len(idx) - keep]) if keep else set(idx)
    return [{**m, "content": str(m["content"])[:300] + " ...(older output trimmed)"} if i in old and len(str(m.get("content") or "")) > 300 else m
            for i, m in enumerate(messages)]


def parse_system(system):
    base, _, mode = system.partition("@")
    if not mode:
        return base, None
    m = MODE_RE.match(mode)
    if not m:
        raise SystemExit("unknown mode " + mode)
    kind, k, deep = m.group(1), int(m.group(2) or 0), bool(m.group(3))
    check = bool(m.group(4)) or kind == "dc"
    return base, {"kind": kind, "k": k, "deep": deep, "check": check,
                  "attempts": 1 if kind == "dc" else k if kind in ("vote", "rank") else k + 1}


CTX_TRIMS = [0]


class LPLLM(R.LLM):
    """run.LLM with the same sampling; judge calls (think=True) also keep token logprobs, doer calls can draw n samples."""

    def _kw(self, messages, tools, tool_choice, think, max_tokens, temperature):
        kw = dict(model=self.model, messages=messages, max_tokens=max_tokens,
                  temperature=temperature if temperature is not None else (0.6 if think else 0.7),
                  top_p=0.95 if think else 0.8,
                  extra_body={"chat_template_kwargs": {"enable_thinking": think}, "top_k": 20})
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = tool_choice or "auto"
        return kw

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=1024, temperature=None):
        if think and "Qwen3.5" in self.model:
            max_tokens = max(max_tokens, 4096)  # Qwen3.5 thinks ~1.1k tokens per verdict; at 1536 half its verdicts were cut off unparsed
        kw = self._kw(messages, tools, tool_choice, think, max_tokens, temperature)
        if think:
            kw.update(logprobs=True, top_logprobs=5)
        r = await self.create(kw)
        ch = r.choices[0]
        if think:
            LP.set(ch.logprobs.content if ch.logprobs else None)
        return ch.message, r.usage.prompt_tokens, r.usage.completion_tokens

    async def create(self, kw):
        import openai
        for keep in (None, 4, 1, 0):
            k2 = kw if keep is None else {**kw, "messages": trim_old_outputs(kw["messages"], keep)}
            try:
                return await self.c.chat.completions.create(**k2)
            except openai.BadRequestError as ex:
                if CTX_ERR not in str(ex) or keep == 0:
                    raise
                CTX_TRIMS[0] += 1

    async def sample(self, messages, tools, n=1):
        kw = self._kw(messages, tools, None, False, 1024, None)
        if n > 1:
            kw["n"] = n
        r = await self.create(kw)
        return [c.message for c in r.choices], r.usage.prompt_tokens, r.usage.completion_tokens


def _p_good(toks, starts, pos, good, bads):
    """Judge's probability that the label starting at char pos is `good`, from the top 5 alternatives at that token."""
    i = bisect.bisect_right(starts, pos) - 1
    t = toks[i]
    off = pos - starts[i]
    pg = pb = 0.0
    for alt in (t.top_logprobs or []):
        if alt.token[:off] != t.token[:off]:
            continue
        s = alt.token[off:].strip().lower()
        if not s:
            continue
        isg = good.startswith(s) or s.startswith(good)
        isb = any(b.startswith(s) or s.startswith(b) for b in bads)
        if isg and not isb:
            pg += math.exp(alt.logprob)
        elif isb and not isg:
            pb += math.exp(alt.logprob)
    if pg + pb == 0:
        return None
    return pg / (pg + pb)


def p_flag(v, toks):
    """1 - P(on_track) * P(none) at the verdict tokens; falls back to the hard verdict."""
    flagged = v["q1"] == "off_track" or v["q2"] != "none"
    hard = 1.0 if flagged else 0.0
    if v.get("repeat") or not toks:
        return hard
    text, starts, n = "", [], 0
    for t in toks:
        starts.append(n); n += len(t.token); text += t.token
    ms = list(R.VERDICT_RE.finditer(text))
    if not ms:
        return hard
    m = ms[-1]
    p1 = _p_good(toks, starts, m.start(1), "on_track", ["off_track"])
    p2 = _p_good(toks, starts, m.start(2), "none", ["made_up_value", "false_claim"])
    p1 = (0.0 if v["q1"] == "off_track" else 1.0) if p1 is None else p1
    p2 = (0.0 if v["q2"] != "none" else 1.0) if p2 is None else p2
    return 1.0 - p1 * p2


def _args(a):
    try:
        return json.loads(a)
    except Exception:
        return a


def signature(m):
    tcs = m.tool_calls or []
    if not tcs:
        return ("MSG",)
    out = []
    for tc in tcs:
        try:
            a = json.dumps(json.loads(tc.function.arguments), sort_keys=True)
        except Exception:
            a = tc.function.arguments
        out.append((tc.function.name, a))
    return tuple(out)


class Turn:
    """One user turn of the doer loop with rollback style corrections. Env specifics come in as callables."""

    def __init__(self, ep, plan, tools, allowed, t):
        self.ep, self.plan, self.tools, self.allowed, self.t = ep, plan, tools, allowed, t
        self.turn_calls, self.turn_steps = [], []
        self.marks = []  # (len(msgs) before an appended step, all its calls failed)
        self.checks, self.oracle_start = 0, None

    def ctx(self):
        ep = self.ep
        return {"requests": ep.requests, "plan": self.plan, "recent": ep.recent, "turn_calls": self.turn_calls,
                "tools": ep.ctx_tools, **ep.ctx_extra}

    async def judge(self, step, repeat=False):
        ep = self.ep
        if repeat:
            v = R.Verdict(q1="off_track", q2="none", q3="needed", jin=0, jout=0, repeat=True)
            return v, True, 1.0
        LP.set(None)
        v = await ep.judge.judge(self.ctx(), step)
        ep.st["judge_in"] += v["jin"]; ep.st["judge_out"] += v["jout"]; ep.st["judge_calls"] += 1
        flagged = v["q1"] == "off_track" or v["q2"] != "none"
        return v, flagged, p_flag(v, LP.get())

    async def try_step(self, cand, gate=True):
        """Run one candidate. Returns ("done",) ("ran",) ("partial",) or ("flagged", p)."""
        ep, msgs, st = self.ep, self.ep.msgs, self.ep.st
        tcs = cand.tool_calls or []
        if not tcs:
            text = R.strip_think(cand.content)
            rec = {"turn": self.t, "kind": "msg", "text": text[:500], "forced_run": not gate}
            if gate:
                v, flagged, p = await self.judge({"kind": "msg", "text": text, "ev": []})
                rec.update(q1=v["q1"], q2=v["q2"], p_flag=round(p, 4), rolled_back=flagged, jin=v["jin"], jout=v["jout"])
                if flagged:
                    ep.steps_log.append(rec)
                    return ("flagged", p)
            ep.steps_log.append(rec)
            ep.last_text = text
            msgs.append({"role": "assistant", "content": text})
            return ("done",)
        amsg = {"role": "assistant", "content": R.strip_think(cand.content) or None,
                "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tcs]}
        tmsgs, executed, all_failed, result = [], [], True, ("ran",)
        for i, tc in enumerate(tcs):
            cs, args, err = R.call_string(tc.function.name, tc.function.arguments, self.allowed)
            ev = P.evidence(args, "\n".join(ep.requests), "\n".join(ep.all_outputs), ep.docs_text, ep.env_text) if args else []
            step = {"kind": "call", "name": tc.function.name, "args": args or {}, "text": cs or f"{tc.function.name}({tc.function.arguments})", "ev": ev}
            rec = {"turn": self.t, "kind": "call", "call": step["text"][:400], "ev": [w for _, _, w in ev], "forced_run": not gate}
            if err:
                out = err
            else:
                if gate:
                    repeat = ep.last_failed.get(cs, 0) >= 1 and not isinstance(ep.judge, R.NoJudge)
                    v, flagged, p = await self.judge(step, repeat)
                    rec.update(q1=v["q1"], q2=v["q2"], q3=v["q3"], p_flag=round(p, 4), repeat=bool(v.get("repeat")), jin=v["jin"], jout=v["jout"])
                    if flagged:
                        rec["rolled_back"] = True
                        ep.steps_log.append(rec)
                        if i == 0:
                            return ("flagged", p)
                        amsg["tool_calls"] = amsg["tool_calls"][:i]  # keep the calls that ran, drop the flagged one and the rest
                        result = ("partial",)
                        break
                    if v["q3"] == "not_needed":
                        st["asks"] += 1  # the scripted user always approves
                out, record, failed = ep.execute(cs, tc.function.name, args or {})
                if record:
                    executed.append(cs)
                    self.turn_calls.append((cs, out)); ep.recent.append((cs, out)); ep.all_outputs.append(str(out))
                if failed:
                    ep.last_failed[cs] = ep.last_failed.get(cs, 0) + 1
                else:
                    all_failed = False
            rec["out"] = str(out)[:300]
            tmsgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
            ep.steps_log.append(rec)
        self.marks.append((len(msgs), all_failed))
        msgs.append(amsg); msgs.extend(tmsgs)
        if executed:
            self.turn_steps.append(executed)
        return result

    async def rank(self, cands):
        """Highest reward model score among the distinct candidates; unanimous samples skip the ranker."""
        import httpx
        import rank_format as rankers
        ep, st = self.ep, self.ep.st
        uniq = list({signature(c): c for c in cands}.values())
        if len(uniq) == 1:
            st["vote_skips"] += 1
            return uniq[0]
        docs = json.loads(ep.docs_text)
        items = []
        for c in uniq:
            tcs = c.tool_calls or []
            resp = "\n".join(rankers.call_text(tc.function.name, _args(tc.function.arguments)) for tc in tcs) if tcs else R.strip_think(c.content)
            items.append(rankers.state_messages(ep.requests, ep.recent, docs, resp))
        ts = time.time()
        async with httpx.AsyncClient(timeout=600) as cl:
            scores = (await cl.post(RANKER_URL, json={"items": items})).json()["scores"]
        st["ranked"] += 1; st["interventions"] += 1
        best = max(range(len(uniq)), key=lambda i: -1e9 if scores[i] is None else scores[i])
        ep.steps_log.append({"turn": self.t, "kind": "rank", "n": len(uniq), "scores": scores, "pick": best, "s": time.time() - ts})
        return uniq[best]

    async def closed(self, mode):
        """Done check at a closing message: True ends the turn; False drops the message and adds one neutral line."""
        if not mode["check"] or self.checks >= 2:
            return True
        ep, st = self.ep, self.ep.st
        done = await self.done_check()
        st["done_checks"] += 1
        ep.steps_log.append({"turn": self.t, "kind": "done_check", "done": done})
        if done:
            return True
        self.checks += 1; st["not_done"] += 1; st["interventions"] += 1
        ep.msgs.pop()
        ep.msgs.append({"role": "user", "content": UNFINISHED})
        return False

    async def done_check(self):
        ep = self.ep
        j = getattr(ep.judge, "inner", ep.judge)
        if hasattr(j, "_state_after"):  # oracle: done iff the state matches the turn's reference end state
            cur = LV.CUR.get()
            e = cur["e"]
            live = j._live(e, f"{cur['system']}_r{cur['run']}")
            gold = list(e["gold"][self.t])
            called = {c.split("(")[0] for step in self.turn_steps for c in step}
            # state only would miss skipped read calls (cat, ls, get_*), so every reference function must also have been called
            return R.snapshot(live) == j._state_after(e, self.oracle_start, gold) and {g.split("(")[0] for g in gold} <= called
        if not hasattr(j, "llm"):  # step classifiers (feature trees, Jev): their verdict on the closing message
            v = await ep.judge.judge(self.ctx(), {"kind": "msg", "text": ep.last_text, "ev": []})
            ep.st["judge_in"] += v.get("jin", 0); ep.st["judge_out"] += v.get("jout", 0)
            return v["q1"] == "on_track" and v["q2"] == "none"
        lines = ["USER REQUESTS (latest last):"] + [f"- {P.cut(r, 500)}" for r in ep.requests[-4:]]
        lines.append("CALLS FOR THE LATEST REQUEST:")
        lines += [f"- {P.cut(c, 200)} -> {P.cut(o, 200)}" for c, o in self.turn_calls[-12:]] or ["- (none)"]
        lines.append("CLOSING MESSAGE: " + P.cut(ep.last_text, 600))
        llm = getattr(j, "llm", None) or ep.llm
        msg, pin, pout = await llm.chat([{"role": "system", "content": DONE_GUIDE}, {"role": "user", "content": "\n".join(lines)}], think=True, max_tokens=1536)
        ep.st["judge_in"] += pin; ep.st["judge_out"] += pout
        m = DONE_RE.findall(R.strip_think(msg.content) or "") or DONE_RE.findall(msg.content or "")
        return not m or m[-1].lower() == "yes"

    def deep_rollback(self):
        """Drop this turn's trailing steps whose calls all failed (no state change, so the context stays true)."""
        dropped = False
        while self.marks and self.marks[-1][1]:
            idx, _ = self.marks.pop()
            del self.ep.msgs[idx:]
            dropped = True
        return dropped

    async def run(self, mode):
        ep, st = self.ep, self.ep.st
        steps = samples = 0
        attempts, pool, deep_used = [], [], False
        j = getattr(ep.judge, "inner", ep.judge)
        if mode["check"] and hasattr(j, "_state_after"):
            import copy
            cur = LV.CUR.get()
            self.oracle_start = {c: copy.deepcopy(o) for c, o in j._live(cur["e"], f"{cur['system']}_r{cur['run']}").items()}
        budget = R.MAX_STEPS * (mode["attempts"] + 1)
        while True:
            if steps >= R.MAX_STEPS or samples >= budget:
                return True
            if not pool:
                n = mode["k"] if mode["kind"] in ("vote", "rank") else 1
                extra = [{"role": "user", "content": HINT}] if mode["kind"] == "rbh" and attempts else []
                ts = time.time()
                cands, pin, pout = await ep.llm.sample(ep.msgs + extra, self.tools, n)
                st["agent_in"] += pin; st["agent_out"] += pout; st["llm_calls"] += 1; samples += 1
                ep.steps_log.append({"turn": self.t, "kind": "sample", "n": n, "hint": bool(extra), "in": pin, "out_tok": pout, "s": time.time() - ts})
                if mode["kind"] == "rank":
                    best = await self.rank(cands)
                    r = await self.try_step(best, gate=False)
                    steps += 1; st["steps"] += 1
                    if r[0] == "done" and await self.closed(mode):
                        return False
                    continue
                if mode["kind"] == "vote":
                    groups = Counter(signature(c) for c in cands)
                    if len(groups) == 1:
                        st["vote_skips"] += 1
                        r = await self.try_step(cands[0], gate=False)
                        steps += 1; st["steps"] += 1
                        if r[0] == "done" and await self.closed(mode):
                            return False
                        continue
                    order = {s: k for k, (s, _) in enumerate(groups.most_common())}
                    cands = sorted(cands, key=lambda c: order[signature(c)])
                pool = list(cands)
            cand = pool.pop(0)
            r = await self.try_step(cand, gate=mode["kind"] != "dc")
            if r[0] == "done":
                steps += 1; st["steps"] += 1
                if await self.closed(mode):
                    return False
                attempts, pool = [], []
                continue
            if r[0] in ("ran", "partial"):
                steps += 1; st["steps"] += 1
                if r[0] == "partial":
                    st["interventions"] += 1; st["resamples"] += 1
                attempts, pool = [], []
                continue
            # flagged: nothing ran, the attempt is dropped
            st["interventions"] += 1
            attempts.append((r[1], len(attempts), cand))
            if mode["deep"] and not deep_used and not (cand.tool_calls or []) and self.deep_rollback():
                deep_used = True
                st["deep_rollbacks"] += 1
                attempts, pool = [], []
                continue
            if len(attempts) >= mode["attempts"] or (mode["kind"] == "vote" and not pool):
                st["fallbacks"] += 1
                best = min(attempts, key=lambda a: (a[0], a[1]))[2]
                r = await self.try_step(best, gate=False)
                steps += 1; st["steps"] += 1
                if r[0] == "done" and await self.closed(mode):
                    return False
                attempts, pool = [], []
                continue
            st["resamples"] += 1
            if mode["kind"] != "vote":
                pool = []


class Ep:
    def __init__(self, llm, judge, docs_text, env_text, ctx_tools, ctx_extra, execute):
        self.llm, self.judge, self.docs_text, self.env_text = llm, judge, docs_text, env_text
        self.ctx_tools, self.ctx_extra, self.execute = ctx_tools, ctx_extra, execute
        self.msgs = [{"role": "system", "content": P.DOER_SYS}]
        self.requests, self.all_outputs, self.recent, self.steps_log = [], [], [], []
        self.st, self.last_failed, self.last_text = Counter(), {}, ""

    async def plan(self, user_text, tools, t):
        ts = time.time()
        pm, pin, pout = await self.llm.chat(self.msgs + [{"role": "user", "content": user_text + "\n\n" + P.PLANNER_SYS}],
                                            tools=tools, tool_choice="none", max_tokens=400)
        plan = R.strip_think(pm.content)[:1500]
        self.st["agent_in"] += pin; self.st["agent_out"] += pout; self.st["llm_calls"] += 1
        self.steps_log.append({"turn": t, "kind": "plan", "text": plan, "in": pin, "out": pout, "s": time.time() - ts})
        self.msgs.append({"role": "user", "content": user_text + ("\n\nPlan for this request:\n" + plan if plan else "")})
        return plan


ROW_EXTRA = ("resamples", "fallbacks", "vote_skips", "deep_rollbacks", "judge_calls", "ranked", "done_checks", "not_done")


def row_of(system, e, run, passed, valid, etype, empty_fail, error, turns, st, t0):
    row = {"system": system, "id": e["id"], "version": e["version"], "scenario": e["scenario"], "run": run,
           "passed": passed, "bfcl_valid": valid, "error_type": etype, "empty_turn_fail": empty_fail, "harness_error": error,
           "turns": turns, "steps": st["steps"], "llm_calls": st["llm_calls"], "interventions": st["interventions"],
           "fresh_doers": 0, "asks": st["asks"], "agent_in": st["agent_in"], "agent_out": st["agent_out"],
           "judge_in": st["judge_in"], "judge_out": st["judge_out"], "seconds": time.time() - t0}
    row.update({k: st[k] for k in ROW_EXTRA})
    return row


async def bfcl_episode(e, run, system, llm, judge, log, mode):
    U = R.U
    t0 = time.time()
    sysname = re.sub(r"\W", "_", system)
    model_name = f"{sysname}_r{run}"
    LV.CUR.set({"id": e["id"], "run": run, "version": e["version"], "scenario": e["scenario"], "gold": e["gold"], "e": e, "system": sysname})
    test_id, lc = e["id"], e["version"] == "long_context"
    R.reset_instances(model_name, test_id)
    _, inst = U.execute_multi_turn_func_call([], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)
    docs = [d for c in e["involved_classes"] for d in R.docs_for(c)]
    env_text = json.dumps(e["initial_config"], default=str) + json.dumps(R.snapshot(inst), default=str)
    if "TravelAPI" in e["involved_classes"]:
        env_text += str(U.execute_multi_turn_func_call(["list_all_airports()"], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)[0])
    missed = {int(k): v for k, v in (e.get("missed_function") or {}).items()}
    held = {n for names in missed.values() for n in names}
    active = [d for d in docs if d["name"] not in held]

    def execute(cs, name, args):
        res, _ = U.execute_multi_turn_func_call([cs], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)
        out = res[0]
        return out, True, str(out).startswith("Error")

    ep = Ep(llm, judge, json.dumps(docs), env_text, None, {}, execute)
    decoded, empty_fail, error, forced = [], 0, None, False
    try:
        for t, turn in enumerate(e["question"]):
            if t in missed:
                active += [d for d in docs if d["name"] in missed[t]]
            tools = [R.to_tool(d) for d in active]
            allowed = {d["name"] for d in active}
            ep.ctx_tools = active
            user_text = "\n".join(m["content"] for m in turn) if turn else R.ADDED_FUNC_PROMPT
            ep.requests.append(user_text)
            before = R.snapshot(inst) if not e["gold"][t] else None
            plan = await ep.plan(user_text, tools, t)
            tr = Turn(ep, plan, tools, allowed, t)
            forced = await tr.run(mode)
            decoded.append(tr.turn_steps)
            if before is not None and R.snapshot(inst) != before:
                empty_fail = 1
            if forced:
                break
    except Exception as ex:
        error = f"{type(ex).__name__}: {str(ex)[:300]}"
    if error or forced:
        verdict = {"valid": False, "error_type": "harness:" + ("forced_quit" if forced else "error")}
    else:
        try:
            verdict = R.multi_turn_checker(decoded, e["gold"], e, "multi_turn_" + e["version"], model_name)
        except Exception as ex:
            verdict = {"valid": False, "error_type": "checker:exception", "error_message": str(ex)[:300]}
    R.reset_instances(model_name, test_id)
    valid = bool(verdict.get("valid"))
    row = row_of(system, e, run, valid and not empty_fail, valid, verdict.get("error_type"), empty_fail, error, len(e["question"]), ep.st, t0)
    log.write(json.dumps({"id": test_id, "run": run, "system": system, "steps": ep.steps_log, "decoded": decoded}) + "\n"); log.flush()
    return row


async def ad_episode(e, run, system, llm, judge, log, mode):
    import agentdojo_run as AD
    from agentdojo.functions_runtime import FunctionsRuntime, FunctionCall
    t0 = time.time()
    suite, user_task = e["suite_obj"], e["task"]
    env = suite.load_and_inject_default_environment({})
    task_env = user_task.init_environment(env)
    pre_env = task_env.model_copy(deep=True)
    runtime = FunctionsRuntime(suite.tools)
    tools = [AD.function_to_tool(f) for f in suite.tools]
    allowed = {f.name for f in suite.tools}
    docs_text = json.dumps([{"name": f.name, "description": f.description or "", "parameters": f.parameters.model_json_schema()} for f in suite.tools])
    traces = []

    def execute(cs, name, args):
        res, err = runtime.run_function(task_env, name, args)
        if err:
            return f"Error: {err}", False, True
        traces.append(FunctionCall(function=name, args=args))
        return AD.format_tool_result(res), True, False

    ep = Ep(llm, judge, docs_text, task_env.model_dump_json(), suite.tools,
            {"suite": e["suite"], "irreversible": AD.IRREVERSIBLE.get(e["suite"], set())}, execute)
    decoded, error, forced = [], None, False
    try:
        ep.requests.append(user_task.PROMPT)
        plan = await ep.plan(user_task.PROMPT, tools, 0)
        tr = Turn(ep, plan, tools, allowed, 0)
        forced = await tr.run(mode)
        decoded.append(tr.turn_steps)
    except Exception as ex:
        error = f"{type(ex).__name__}: {str(ex)[:300]}"
    passed, etype = False, None
    if error or forced:
        etype = "harness:" + ("forced_quit" if forced else "error")
    else:
        try:
            u = user_task.utility_from_traces(ep.last_text, pre_env, task_env, traces) if hasattr(user_task, "utility_from_traces") else None
            passed = bool(u) if u is not None else bool(user_task.utility(ep.last_text, pre_env, task_env))
            etype = None if passed else "utility:failed"
        except Exception as ex:
            etype, error = f"checker:exception:{type(ex).__name__}", f"CheckerException: {str(ex)[:300]}"
    row = row_of(system, e, run, passed, passed, etype, 0, error, 1, ep.st, t0)
    log.write(json.dumps({"id": e["id"], "run": run, "system": system, "steps": ep.steps_log, "decoded": decoded}) + "\n"); log.flush()
    return row


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="bfcl", choices=["bfcl", "agentdojo"])
    ap.add_argument("--system", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--versions", default="base,miss_param,miss_func,long_context")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-8B-AWQ")
    ap.add_argument("--judge-url", default="")
    ap.add_argument("--judge-model", default="")
    ap.add_argument("--granite-url", default="http://localhost:8001/v1")
    ap.add_argument("--laya-device", default="cuda:0")
    ap.add_argument("--suites", default="workspace,travel,banking,slack")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base, mode = parse_system(a.system)
    if a.bench == "bfcl":
        sp = R.split()
        json.dump(sp, open(os.path.join(a.out, "split.json"), "w"))
        scen = sp[a.split] if a.split in sp else [int(x) for x in a.split.split(",")]
        if a.limit:
            scen = scen[:a.limit]
        entries = [e for v in a.versions.split(",") for e in R.load_version(v) if e["scenario"] in set(scen)]
    else:
        import agentdojo_run as AD
        entries = AD.load_tasks(a.suites)
        if a.limit:
            entries = entries[:a.limit]
    si, sn = map(int, a.shard.split("/"))
    tag = f"{a.system}_{si}of{sn}"
    tp = os.path.join(a.out, f"tasks_{tag}.jsonl")
    done = {(r["id"], r["run"]) for r in R.jl(tp)} if os.path.exists(tp) else set()
    jobs = [(e, r) for r in range(a.runs) for e in entries]
    jobs = [j for k, j in enumerate(jobs) if k % sn == si and (j[0]["id"], j[1]) not in done]
    print(f"{a.system} on {a.bench}: {len(jobs)} episodes to run ({len(done)} already done), concurrency {a.concurrency}", flush=True)
    llm = LPLLM(a.base_url, a.model)
    jllm = LPLLM(a.judge_url, a.judge_model or a.model) if a.judge_url else llm
    if a.bench == "bfcl":
        judge = R.make_judge(base, jllm, a)  # laya_run's version: also S1_record, S_oracle
    else:
        import agentdojo_run as AD
        judge = AD.make_judge(base, jllm, a)
    sem = asyncio.Semaphore(a.concurrency)
    tf, lf = open(tp, "a"), open(os.path.join(a.out, f"steps_{tag}.jsonl"), "a")
    t0, finished = time.time(), 0

    async def one(e, r):
        nonlocal finished
        async with sem:
            if mode is None:
                if a.bench == "bfcl":
                    row = await R.episode(e, r, a.system, llm, judge, lf)
                else:
                    import agentdojo_run as AD
                    row = await AD.episode(e, r, a.system, llm, judge, lf)
            elif a.bench == "bfcl":
                row = await bfcl_episode(e, r, a.system, llm, judge, lf, mode)
            else:
                row = await ad_episode(e, r, a.system, llm, judge, lf, mode)
        tf.write(json.dumps(row) + "\n"); tf.flush()
        finished += 1
        if finished % 10 == 0 or finished == len(jobs):
            print(f"{finished}/{len(jobs)} done, {time.time()-t0:.0f}s", flush=True)

    await asyncio.gather(*(one(e, r) for e, r in jobs))
    print("DONE", a.system, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
