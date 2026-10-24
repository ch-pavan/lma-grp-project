# BFCL v4 multi turn harness: planner + doer + per step judge, all against a vLLM OpenAI server.
# usage: python run.py --system S1_none --split test --runs 3 --out results/S1_none [--limit N] [--versions base,miss_param]
import argparse, asyncio, copy, hashlib, json, os, re, sys, time, traceback
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
LB = os.environ.get("BFCL_LB", os.path.join(HERE, "gorilla", "berkeley-function-call-leaderboard"))
sys.path.insert(0, LB)
sys.path.insert(0, HERE)
from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils as U
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.constants.executable_backend_config import MULTI_TURN_FUNC_DOC_FILE_MAPPING
import prompts as P

DATA = os.path.join(LB, "bfcl_eval", "data")
VERSIONS = ["base", "miss_param", "miss_func", "long_context"]
ADDED_FUNC_PROMPT = "I have updated some more functions you can choose from. What about now?"
MAX_STEPS = 20  # BFCL's per turn step limit; blocked attempts count too
# Unsound answer keys (gorilla issues 1367, 1267, 1137, 914); the scenario is dropped in every version.
UNSOUND = {4, 8, 10, 18, 35, 75, 178, 180, 186, 187, 198}
IRREVERSIBLE = set("rm rmdir echo mv cp send_message delete_message post_tweet retweet comment mention create_ticket "
                   "close_ticket resolve_ticket edit_ticket place_order cancel_order withdraw_funds fund_account "
                   "book_flight cancel_booking purchase_insurance register_credit_card fillFuelTank".split())


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def load_version(v):
    q = jl(os.path.join(DATA, f"BFCL_v4_multi_turn_{v}.json"))
    g = {e["id"]: e["ground_truth"] for e in jl(os.path.join(DATA, "possible_answer", f"BFCL_v4_multi_turn_{v}.json"))}
    for e in q:
        e["gold"] = g[e["id"]]
        e["version"] = v
        e["scenario"] = int(e["id"].rsplit("_", 1)[1])
    return q


DOCS = {}
def docs_for(cls):
    if cls not in DOCS:
        DOCS[cls] = jl(os.path.join(DATA, "multi_turn_func_doc", MULTI_TURN_FUNC_DOC_FILE_MAPPING[cls]))
    return DOCS[cls]


def split():
    """Deterministic scenario split: sha256 order of the kept scenario ids, first 100 test, next 15 validation."""
    kept = sorted((i for i in range(200) if i not in UNSOUND), key=lambda i: hashlib.sha256(f"stay-on-task-{i}".encode()).hexdigest())
    return {"test": sorted(kept[:100]), "val": sorted(kept[100:115]), "train": sorted(kept[115:]), "dropped": sorted(UNSOUND)}


TYPE_MAP = {"dict": "object", "float": "number", "tuple": "array", "any": "string", "int": "integer", "list": "array", "bool": "boolean", "str": "string"}
def fix_types(schema):
    schema = copy.deepcopy(schema)
    def walk(s):
        if isinstance(s, dict):
            t = s.get("type")
            if t == "float":
                s["description"] = (s.get("description", "") + " This is a float type value.").strip()
            if t in TYPE_MAP:
                s["type"] = TYPE_MAP[t]
            for k, v in list(s.items()):
                if k in ("properties",):
                    for pv in v.values():
                        walk(pv)
                elif k in ("items", "additionalProperties"):
                    walk(v)
        return s
    return walk(schema)


def to_tool(doc):
    return {"type": "function", "function": {"name": doc["name"], "description": doc.get("description", ""),
                                             "parameters": fix_types(doc.get("parameters", {"type": "dict", "properties": {}}))}}


NAME_RE = re.compile(r"^[A-Za-z_]\w*$")
def call_string(name, args_json, allowed):
    try:
        args = json.loads(args_json) if isinstance(args_json, str) else args_json
    except Exception:
        return None, None, "Error: tool call arguments are not valid JSON."
    if not isinstance(args, dict):
        return None, None, "Error: tool call arguments must be a JSON object."
    if name not in allowed:
        return None, args, f"Error: no tool named {name} is available."
    if not all(NAME_RE.match(k) for k in args):
        return None, args, "Error: invalid argument name."
    return f"{name}({','.join(f'{k}={v!r}' for k, v in args.items())})", args, None


def reset_instances(model_name, test_id):
    for mn in (model_name, model_name + "_eval", model_name + "_ground_truth_eval"):
        prefix = re.sub(r"[-./:]", "_", f"{mn}_{test_id}_")
        for k in [k for k in vars(U) if k.startswith(prefix)]:
            del vars(U)[k]


def snapshot(instances):
    return {c: copy.deepcopy({k: v for k, v in vars(o).items() if not k.startswith("_")}) for c, o in instances.items()}


THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)
def strip_think(s):
    return THINK_RE.sub("", s or "").replace("<think>", "").strip()


class LLM:
    def __init__(self, base_url, model):
        from openai import AsyncOpenAI
        self.c = AsyncOpenAI(base_url=base_url, api_key="x", timeout=900, max_retries=2)
        self.model = model

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=1024, temperature=None):
        kw = dict(model=self.model, messages=messages, max_tokens=max_tokens,
                  temperature=temperature if temperature is not None else (0.6 if think else 0.7),
                  top_p=0.95 if think else 0.8,
                  extra_body={"chat_template_kwargs": {"enable_thinking": think}, "top_k": 20})
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = tool_choice or "auto"
        r = await self.c.chat.completions.create(**kw)
        return r.choices[0].message, r.usage.prompt_tokens, r.usage.completion_tokens


# ---------------- judges ----------------
class Verdict(dict):
    pass


def rule_checks(ctx, step):
    """Plain rules (S2) and the rule fallback for questions a classifier cannot express."""
    q1 = q2 = None
    if step["kind"] == "call":
        if any(w == "nowhere" for _, _, w in step["ev"]):
            q2 = "made_up_value"
        if ctx["plan"] and step["name"] not in ctx["plan"]:
            q1 = "off_track"
    else:
        ok_calls = [o for c, o in ctx["turn_calls"] if not str(o).startswith("Error")]
        if P.SUCCESS_WORDS.search(step["text"]) and not ok_calls:
            q2 = "false_claim"
    return q1 or "on_track", q2 or "none"


class NoJudge:
    name = "S1_none"
    async def judge(self, ctx, step):
        return Verdict(q1="on_track", q2="none", q3="needed", jin=0, jout=0)


class RulesJudge:
    name = "S2_rules"
    async def judge(self, ctx, step):
        q1, q2 = rule_checks(ctx, step)
        q3 = "not_needed" if step.get("name") in IRREVERSIBLE else "needed"  # ask on every irreversible call
        return Verdict(q1=q1, q2=q2, q3=q3, jin=0, jout=0)


VERDICT_RE = re.compile(r"VERDICT\s+Q1\s*=\s*(on_track|off_track)\s+Q2\s*=\s*(none|made_up_value|false_claim)", re.I)
class LLMJudge:
    name = "S3_llm_judge"
    def __init__(self, llm, state_layout="legacy"):
        self.llm = llm
        self.state_layout = state_layout
    async def judge(self, ctx, step):
        build = P.build_state_proposal if self.state_layout == "proposal" else P.build_state
        state = build(ctx["requests"], ctx["plan"], ctx["recent"], step, step["ev"])
        msg, pin, pout = await self.llm.chat([{"role": "system", "content": P.JUDGE_GUIDE}, {"role": "user", "content": state}],
                                             think=True, max_tokens=1536)
        m = VERDICT_RE.search(strip_think(msg.content)) or VERDICT_RE.search(msg.content or "")
        q1, q2 = (m.group(1).lower(), m.group(2).lower()) if m else ("on_track", "none")
        if step["kind"] == "call" and q2 == "false_claim":
            q2 = "none"
        q3 = "not_needed" if step.get("name") in IRREVERSIBLE else "needed"
        return Verdict(q1=q1, q2=q2, q3=q3, jin=pin, jout=pout, parsed=bool(m))


def make_judge(system, llm, args):
    if system == "S1_none":
        return NoJudge()
    if system == "S2_rules":
        return RulesJudge()
    if system == "S3_llm_judge":
        return LLMJudge(llm, getattr(args, "state", "proposal"))
    if system == "S4a_laya":
        from judges_small import LayaJudge
        return LayaJudge(args, rule_checks, IRREVERSIBLE)
    if system == "S4b_granite":
        from judges_small import GraniteJudge
        return GraniteJudge(args, rule_checks, IRREVERSIBLE)
    raise SystemExit("unknown system " + system)


# ---------------- one episode ----------------
async def episode(e, run, system, llm, judge, log):
    t0 = time.time()
    model_name = f"{system}_r{run}"
    test_id = e["id"]
    lc = e["version"] == "long_context"
    reset_instances(model_name, test_id)
    _, inst = U.execute_multi_turn_func_call([], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)

    docs = [d for c in e["involved_classes"] for d in docs_for(c)]
    # environment the agent can read through tools: initial config plus every public attribute of the loaded instances
    env_text = json.dumps(e["initial_config"], default=str) + json.dumps(snapshot(inst), default=str)
    if "TravelAPI" in e["involved_classes"]:  # airport codes are readable through list_all_airports
        env_text += str(U.execute_multi_turn_func_call(["list_all_airports()"], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)[0])
    missed = {int(k): v for k, v in (e.get("missed_function") or {}).items()}
    held = {n for names in missed.values() for n in names}
    active = [d for d in docs if d["name"] not in held]
    docs_text = json.dumps(docs)
    msgs = [{"role": "system", "content": P.DOER_SYS}]
    requests, all_outputs, recent = [], [], []
    decoded, steps_log = [], []
    st = Counter()
    empty_turn_fail = 0
    error = None
    forced = False
    last_failed = {}
    try:
        for t, turn in enumerate(e["question"]):
            if t in missed:
                active += [d for d in docs if d["name"] in missed[t]]
            tools = [to_tool(d) for d in active]
            allowed = {d["name"] for d in active}
            user_text = "\n".join(m["content"] for m in turn) if turn else ADDED_FUNC_PROMPT
            requests.append(user_text)
            before = snapshot(inst) if not e["gold"][t] else None

            plan = ""
            if True:  # every system has the planner
                ts = time.time()
                pm, pin, pout = await llm.chat(msgs + [{"role": "user", "content": user_text + "\n\n" + P.PLANNER_SYS}],
                                               tools=tools, tool_choice="none", max_tokens=400)
                plan = strip_think(pm.content)[:1500]
                st["agent_in"] += pin; st["agent_out"] += pout; st["llm_calls"] += 1
                steps_log.append({"turn": t, "kind": "plan", "text": plan, "in": pin, "out": pout, "s": time.time() - ts})
            msgs.append({"role": "user", "content": user_text + ("\n\nPlan for this request:\n" + plan if plan else "")})
            turn_start = len(msgs)
            good = []  # executed (assistant msg, tool msgs) of this turn, for a fresh doer
            turn_steps, turn_calls = [], []
            flags = 0
            n = 0
            while True:
                n += 1
                if n > MAX_STEPS:
                    forced = True
                    break
                ts = time.time()
                m, pin, pout = await llm.chat(msgs, tools=tools, max_tokens=1024)
                st["agent_in"] += pin; st["agent_out"] += pout; st["llm_calls"] += 1; st["steps"] += 1
                tcs = m.tool_calls or []
                ctx = {"requests": requests, "plan": plan, "recent": recent, "turn_calls": turn_calls, "tools": active}
                if not tcs:
                    text = strip_think(m.content)
                    step = {"kind": "msg", "text": text, "ev": []}
                    v = await judge.judge(ctx, step)
                    st["judge_in"] += v["jin"]; st["judge_out"] += v["jout"]
                    flagged = v["q1"] == "off_track" or v["q2"] != "none"
                    steps_log.append({"turn": t, "kind": "msg", "text": text[:500], "q1": v["q1"], "q2": v["q2"], "blocked": flagged,
                                      "in": pin, "out": pout, "jin": v["jin"], "jout": v["jout"], "s": time.time() - ts})
                    if not flagged:
                        msgs.append({"role": "assistant", "content": text})
                        break
                    st["interventions"] += 1; flags += 1
                    why = "off track" if v["q1"] == "off_track" else "like a claim the tool outputs do not support"
                    if flags >= 2:  # fresh doer from the last good step
                        st["fresh_doers"] += 1
                        del msgs[turn_start:]
                        for a, tm in good:
                            msgs.append(a); msgs.extend(tm)
                    msgs.append({"role": "assistant", "content": text})
                    msgs.append({"role": "user", "content": P.WARNING.format(why=why)})
                    continue

                amsg = {"role": "assistant", "content": strip_think(m.content) or None,
                        "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tcs]}
                tmsgs, executed, blocked_any = [], [], False
                for tc in tcs:
                    cs, args, err = call_string(tc.function.name, tc.function.arguments, allowed)
                    ev = P.evidence(args, "\n".join(requests), "\n".join(all_outputs), docs_text, env_text) if args else []
                    step = {"kind": "call", "name": tc.function.name, "args": args or {}, "text": cs or f"{tc.function.name}({tc.function.arguments})", "ev": ev}
                    rec = {"turn": t, "kind": "call", "call": step["text"][:400], "ev": [w for _, _, w in ev]}
                    if err:
                        out = err
                    else:
                        repeat = last_failed.get(cs, 0) >= 1 and not isinstance(judge, NoJudge)
                        v = await judge.judge(ctx, step) if not repeat else Verdict(q1="off_track", q2="none", q3="needed", jin=0, jout=0, repeat=True)
                        st["judge_in"] += v["jin"]; st["judge_out"] += v["jout"]
                        rec.update(q1=v["q1"], q2=v["q2"], q3=v["q3"], jin=v["jin"], jout=v["jout"], repeat=bool(v.get("repeat")))
                        if v["q1"] == "off_track" or v["q2"] != "none":
                            blocked_any = True
                            st["interventions"] += 1
                            why = ("an exact repeat of a call that already failed" if v.get("repeat") else
                                   "off track" if v["q1"] == "off_track" else "like it uses a value nobody gave")
                            out = P.WARNING.format(why=why)
                            rec["blocked"] = True
                        else:
                            if v["q3"] == "not_needed":
                                st["asks"] += 1  # the scripted user always approves
                                rec["asked"] = True
                            res, _ = U.execute_multi_turn_func_call([cs], e["initial_config"], e["involved_classes"], model_name, test_id, long_context=lc)
                            out = res[0]
                            executed.append(cs)
                            turn_calls.append((cs, out))
                            recent.append((cs, out))
                            all_outputs.append(str(out))
                            if str(out).startswith("Error"):
                                last_failed[cs] = last_failed.get(cs, 0) + 1
                    rec["out"] = str(out)[:300]
                    tmsgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
                    steps_log.append(rec)
                steps_log[-1].update({"in": pin, "out_tok": pout, "s": time.time() - ts})
                if executed:
                    turn_steps.append(executed)
                if blocked_any:
                    flags += 1
                    if flags >= 2 and flags % 2 == 0:  # fresh doer: drop this turn's blocked attempts
                        st["fresh_doers"] += 1
                        del msgs[turn_start:]
                        for a, tm in good:
                            msgs.append(a); msgs.extend(tm)
                msgs.append(amsg); msgs.extend(tmsgs)
                if executed and not blocked_any:
                    good.append((amsg, tmsgs))
            decoded.append(turn_steps)
            if before is not None and snapshot(inst) != before:
                empty_turn_fail = 1
            if forced:
                break
    except Exception as ex:
        error = f"{type(ex).__name__}: {str(ex)[:300]}"

    if error or forced:
        verdict = {"valid": False, "error_type": "harness:" + ("forced_quit" if forced else "error"), "error_message": error}
    else:
        try:
            verdict = multi_turn_checker(decoded, e["gold"], e, "multi_turn_" + e["version"], model_name)
        except Exception as ex:
            verdict = {"valid": False, "error_type": "checker:exception", "error_message": str(ex)[:300]}
    reset_instances(model_name, test_id)
    row = {"system": system, "id": test_id, "version": e["version"], "scenario": e["scenario"], "run": run,
           "passed": bool(verdict.get("valid")) and not empty_turn_fail, "bfcl_valid": bool(verdict.get("valid")),
           "error_type": verdict.get("error_type"), "empty_turn_fail": empty_turn_fail, "harness_error": error,
           "turns": len(e["question"]), "steps": st["steps"], "llm_calls": st["llm_calls"],
           "interventions": st["interventions"], "fresh_doers": st["fresh_doers"], "asks": st["asks"],
           "agent_in": st["agent_in"], "agent_out": st["agent_out"], "judge_in": st["judge_in"], "judge_out": st["judge_out"],
           "seconds": time.time() - t0}
    log.write(json.dumps({"id": test_id, "run": run, "system": system, "steps": steps_log, "decoded": decoded}) + "\n")
    log.flush()
    return row


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--versions", default="base,miss_param,miss_func,long_context")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="scenarios to use, 0 = all in split")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-8B-AWQ")
    ap.add_argument("--granite-url", default="http://localhost:8001/v1")
    ap.add_argument("--laya-device", default="cuda:0")
    ap.add_argument("--state", default="proposal", choices=["proposal", "legacy"],
                    help="judge state for Laya and the LLM judge: proposal = step first, evidence, requests, plan, last calls, 768 token budget")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1", help="i/n: run every n-th episode starting at i")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sp = split()
    json.dump(sp, open(os.path.join(a.out, "split.json"), "w"))
    scen = sp[a.split] if a.split in sp else [int(x) for x in a.split.split(",")]
    if a.limit:
        scen = scen[:a.limit]
    entries = [e for v in a.versions.split(",") for e in load_version(v) if e["scenario"] in set(scen)]
    si, sn = map(int, a.shard.split("/"))
    tag = f"{a.system}_{si}of{sn}"
    done = set()
    tp = os.path.join(a.out, f"tasks_{tag}.jsonl")
    if os.path.exists(tp):
        done = {(r["id"], r["run"]) for r in jl(tp)}
    jobs = [(e, r) for r in range(a.runs) for e in entries]
    jobs = [j for k, j in enumerate(jobs) if k % sn == si and (j[0]["id"], j[1]) not in done]
    print(f"{a.system}: {len(jobs)} episodes to run ({len(done)} already done), concurrency {a.concurrency}", flush=True)
    llm = LLM(a.base_url, a.model)
    judge = make_judge(a.system, llm, a)
    sem = asyncio.Semaphore(a.concurrency)
    tf, lf = open(tp, "a"), open(os.path.join(a.out, f"steps_{tag}.jsonl"), "a")
    t0 = time.time()
    finished = 0

    async def one(e, r):
        nonlocal finished
        async with sem:
            row = await episode(e, r, a.system, llm, judge, lf)
        tf.write(json.dumps(row) + "\n"); tf.flush()
        finished += 1
        if finished % 10 == 0 or finished == len(jobs):
            print(f"{finished}/{len(jobs)} done, {time.time()-t0:.0f}s", flush=True)

    await asyncio.gather(*(one(e, r) for e, r in jobs))
    print("DONE", a.system, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
