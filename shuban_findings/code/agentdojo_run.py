# AgentDojo user tasks harness: planner + doer + per step judge against OpenAI server.
import argparse, asyncio, json, os, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run as R
import prompts as P
from run import LLM, NoJudge, Verdict, strip_think, call_string

from agentdojo.benchmark import get_suite
from agentdojo.functions_runtime import FunctionsRuntime, FunctionCall

BENCHMARK_VERSION = "v1.2.2"
SUITES = ["workspace", "travel", "banking", "slack"]
MAX_STEPS = 20

# Per suite irreversible tools for S2 asks identified from tool docs
IRREVERSIBLE = {
    "workspace": {
        "send_email",
        "delete_email",
        "create_calendar_event",
        "cancel_calendar_event",
        "reschedule_calendar_event",
        "add_calendar_event_participants",
        "append_to_file",
        "create_file",
        "delete_file",
        "share_file",
    },
    "travel": {
        "reserve_hotel",
        "reserve_car_rental",
        "reserve_restaurant",
        "send_email",
        "create_calendar_event",
        "cancel_calendar_event",
    },
    "banking": {
        "send_money",
        "schedule_transaction",
        "update_scheduled_transaction",
        "update_password",
        "update_user_info",
    },
    "slack": {
        "send_direct_message",
        "send_channel_message",
        "add_user_to_channel",
        "invite_user_to_slack",
        "remove_user_from_slack",
        "post_webpage",
    },
}

ALL_IRREVERSIBLE = set().union(*IRREVERSIBLE.values())


def function_to_tool(func):
    # Convert AgentDojo function into an OpenAI tool schema
    return {
        "type": "function",
        "function": {
            "name": func.name,
            "description": func.description or "",
            "parameters": func.parameters.model_json_schema(),
        },
    }


def format_tool_result(res):
    # Convert tool execution return value into a string
    if res is None:
        return "None"
    if hasattr(res, "model_dump"):
        return json.dumps(res.model_dump(), default=str)
    if isinstance(res, list):
        items = [x.model_dump() if hasattr(x, "model_dump") else x for x in res]
        return json.dumps(items, default=str)
    return str(res)


class RulesJudge:
    name = "S2_rules"

    def __init__(self, irreversible=None):
        self.irreversible = irreversible or ALL_IRREVERSIBLE

    async def judge(self, ctx, step):
        q1, q2 = R.rule_checks(ctx, step)
        irr = ctx.get("irreversible", self.irreversible)
        q3 = "not_needed" if step.get("name") in irr else "needed"
        return Verdict(q1=q1, q2=q2, q3=q3, jin=0, jout=0)


class LLMJudge:
    name = "S3_llm_judge"

    def __init__(self, llm, irreversible=None):
        self.llm = llm
        self.irreversible = irreversible or ALL_IRREVERSIBLE

    async def judge(self, ctx, step):
        state = P.build_state(ctx["requests"], ctx["plan"], ctx["recent"], step, step["ev"])
        msg, pin, pout = await self.llm.chat(
            [{"role": "system", "content": P.JUDGE_GUIDE}, {"role": "user", "content": state}],
            think=True,
            max_tokens=1536,
        )
        m = R.VERDICT_RE.search(strip_think(msg.content)) or R.VERDICT_RE.search(msg.content or "")
        q1, q2 = (m.group(1).lower(), m.group(2).lower()) if m else ("on_track", "none")
        if step["kind"] == "call" and q2 == "false_claim":
            q2 = "none"
        irr = ctx.get("irreversible", self.irreversible)
        q3 = "not_needed" if step.get("name") in irr else "needed"
        return Verdict(q1=q1, q2=q2, q3=q3, jin=pin, jout=pout, parsed=bool(m))


def make_judge(system, llm, args=None):
    if system == "S1_none":
        return NoJudge()
    if system == "S2_rules":
        return RulesJudge()
    if system == "S3_llm_judge":
        return LLMJudge(llm)
    if system == "S4a_laya":
        from judges_small import LayaJudge
        return LayaJudge(args, R.rule_checks, ALL_IRREVERSIBLE)
    if system == "S4b_granite":
        from judges_small import GraniteJudge
        return GraniteJudge(args, R.rule_checks, ALL_IRREVERSIBLE)
    raise SystemExit("unknown system " + system)


def load_tasks(suites_filter=None):
    # Load all user tasks for the specified benchmark suites
    selected = [s.strip() for s in (suites_filter or "workspace,travel,banking,slack").split(",") if s.strip()]
    tasks = []
    for s_name in selected:
        suite = get_suite(BENCHMARK_VERSION, s_name)
        for tid, task in suite.user_tasks.items():
            tasks.append({
                "suite": s_name,
                "task_id": tid,
                "id": f"{s_name}:{tid}",
                "scenario": f"{s_name}:{tid}",
                "version": "agentdojo",
                "task": task,
                "suite_obj": suite,
            })
    return tasks


async def episode(e, run, system, llm, judge, log):
    t0 = time.time()
    test_id = e["id"]
    suite_name = e["suite"]
    suite = e["suite_obj"]
    user_task = e["task"]

    # Fresh environment initialized from the suite
    env = suite.load_and_inject_default_environment({})
    task_env = user_task.init_environment(env)
    pre_env = task_env.model_copy(deep=True)
    runtime = FunctionsRuntime(suite.tools)

    tools = [function_to_tool(f) for f in suite.tools]
    allowed = {f.name for f in suite.tools}
    docs_text = json.dumps([{"name": f.name, "description": f.description or "",
                            "parameters": f.parameters.model_json_schema()} for f in suite.tools])
    env_text = task_env.model_dump_json()
    user_text = user_task.PROMPT

    msgs = [{"role": "system", "content": P.DOER_SYS}]
    requests = [user_text]
    all_outputs = []
    recent = []
    decoded = []
    steps_log = []
    st = Counter()
    error = None
    forced = False
    last_failed = {}
    traces = []
    model_output_text = ""

    try:
        # Planner step generates an outline of planned calls
        ts = time.time()
        pm, pin, pout = await llm.chat(
            msgs + [{"role": "user", "content": user_text + "\n\n" + P.PLANNER_SYS}],
            tools=tools,
            tool_choice="none",
            max_tokens=400,
        )
        plan = strip_think(pm.content)[:1500]
        st["agent_in"] += pin
        st["agent_out"] += pout
        st["llm_calls"] += 1
        steps_log.append({"turn": 0, "kind": "plan", "text": plan, "in": pin, "out": pout, "s": time.time() - ts})

        msgs.append({"role": "user", "content": user_text + ("\n\nPlan for this request:\n" + plan if plan else "")})
        turn_start = len(msgs)
        good = []
        turn_steps = []
        turn_calls = []
        flags = 0
        n = 0

        while True:
            n += 1
            if n > MAX_STEPS:
                forced = True
                break
            ts = time.time()
            m, pin, pout = await llm.chat(msgs, tools=tools, max_tokens=1024)
            st["agent_in"] += pin
            st["agent_out"] += pout
            st["llm_calls"] += 1
            st["steps"] += 1
            tcs = m.tool_calls or []
            ctx = {
                "requests": requests,
                "plan": plan,
                "recent": recent,
                "turn_calls": turn_calls,
                "tools": suite.tools,
                "suite": suite_name,
                "irreversible": IRREVERSIBLE.get(suite_name, set()),
            }

            if not tcs:
                text = strip_think(m.content)
                model_output_text = text
                step = {"kind": "msg", "text": text, "ev": []}
                v = await judge.judge(ctx, step)
                st["judge_in"] += v["jin"]
                st["judge_out"] += v["jout"]
                flagged = v["q1"] == "off_track" or v["q2"] != "none"
                steps_log.append({
                    "turn": 0,
                    "kind": "msg",
                    "text": text[:500],
                    "q1": v["q1"],
                    "q2": v["q2"],
                    "blocked": flagged,
                    "in": pin,
                    "out": pout,
                    "jin": v["jin"],
                    "jout": v["jout"],
                    "s": time.time() - ts,
                })
                if not flagged:
                    msgs.append({"role": "assistant", "content": text})
                    break
                st["interventions"] += 1
                flags += 1
                why = "off track" if v["q1"] == "off_track" else "like a claim the tool outputs do not support"
                if flags >= 2:
                    st["fresh_doers"] += 1
                    del msgs[turn_start:]
                    for a, tm in good:
                        msgs.append(a)
                        msgs.extend(tm)
                msgs.append({"role": "assistant", "content": text})
                msgs.append({"role": "user", "content": P.WARNING.format(why=why)})
                continue

            amsg = {
                "role": "assistant",
                "content": strip_think(m.content) or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tcs
                ],
            }
            tmsgs, executed, blocked_any = [], [], False
            for tc in tcs:
                cs, args, err = call_string(tc.function.name, tc.function.arguments, allowed)
                ev = P.evidence(args, "\n".join(requests), "\n".join(all_outputs), docs_text, env_text) if args else []
                step = {
                    "kind": "call",
                    "name": tc.function.name,
                    "args": args or {},
                    "text": cs or f"{tc.function.name}({tc.function.arguments})",
                    "ev": ev,
                }
                rec = {"turn": 0, "kind": "call", "call": step["text"][:400], "ev": [w for _, _, w in ev]}
                if err:
                    out = err
                else:
                    repeat = last_failed.get(cs, 0) >= 1 and not isinstance(judge, NoJudge)
                    v = (
                        await judge.judge(ctx, step)
                        if not repeat
                        else Verdict(q1="off_track", q2="none", q3="needed", jin=0, jout=0, repeat=True)
                    )
                    st["judge_in"] += v["jin"]
                    st["judge_out"] += v["jout"]
                    rec.update(
                        q1=v["q1"],
                        q2=v["q2"],
                        q3=v["q3"],
                        jin=v["jin"],
                        jout=v["jout"],
                        repeat=bool(v.get("repeat")),
                    )
                    if v["q1"] == "off_track" or v["q2"] != "none":
                        blocked_any = True
                        st["interventions"] += 1
                        why = (
                            "an exact repeat of a call that already failed"
                            if v.get("repeat")
                            else "off track"
                            if v["q1"] == "off_track"
                            else "like it uses a value nobody gave"
                        )
                        out = P.WARNING.format(why=why)
                        rec["blocked"] = True
                    else:
                        if v["q3"] == "not_needed":
                            st["asks"] += 1
                            rec["asked"] = True
                        res, err_msg = runtime.run_function(task_env, tc.function.name, args or {})
                        if err_msg:
                            out = f"Error: {err_msg}"
                            last_failed[cs] = last_failed.get(cs, 0) + 1
                        else:
                            out = format_tool_result(res)
                            executed.append(cs)
                            turn_calls.append((cs, out))
                            recent.append((cs, out))
                            all_outputs.append(str(out))
                            traces.append(FunctionCall(function=tc.function.name, args=args or {}))
                rec["out"] = str(out)[:300]
                tmsgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
                steps_log.append(rec)
            steps_log[-1].update({"in": pin, "out_tok": pout, "s": time.time() - ts})
            if executed:
                turn_steps.append(executed)
            if blocked_any:
                flags += 1
                if flags >= 2 and flags % 2 == 0:
                    st["fresh_doers"] += 1
                    del msgs[turn_start:]
                    for a, tm in good:
                        msgs.append(a)
                        msgs.extend(tm)
            msgs.append(amsg)
            msgs.extend(tmsgs)
            if executed and not blocked_any:
                good.append((amsg, tmsgs))
        decoded.append(turn_steps)
    except Exception as ex:
        error = f"{type(ex).__name__}: {str(ex)[:300]}"

    passed = False
    verdict_error_type = None
    if error or forced:
        verdict_error_type = "harness:" + ("forced_quit" if forced else "error")
    else:
        try:
            # Check utility from traces if available otherwise regular utility
            u_trace = None
            if hasattr(user_task, "utility_from_traces"):
                u_trace = user_task.utility_from_traces(model_output_text, pre_env, task_env, traces)
            if u_trace is not None:
                passed = bool(u_trace)
            else:
                passed = bool(user_task.utility(model_output_text, pre_env, task_env))
            if not passed:
                verdict_error_type = "utility:failed"
        except Exception as ex:
            passed = False
            verdict_error_type = f"checker:exception:{type(ex).__name__}"
            error = f"CheckerException: {str(ex)[:300]}"

    row = {
        "system": system,
        "id": test_id,
        "version": "agentdojo",
        "scenario": e["scenario"],
        "run": run,
        "passed": passed,
        "bfcl_valid": passed,
        "error_type": verdict_error_type,
        "empty_turn_fail": 0,
        "harness_error": error,
        "turns": 1,
        "steps": st["steps"],
        "llm_calls": st["llm_calls"],
        "interventions": st["interventions"],
        "fresh_doers": st["fresh_doers"],
        "asks": st["asks"],
        "agent_in": st["agent_in"],
        "agent_out": st["agent_out"],
        "judge_in": st["judge_in"],
        "judge_out": st["judge_out"],
        "seconds": time.time() - t0,
    }
    if log:
        log.write(
            json.dumps({"id": test_id, "run": run, "system": system, "steps": steps_log, "decoded": decoded}) + "\n"
        )
        log.flush()
    return row


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--versions", default="agentdojo")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="tasks to use, 0 = all")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-8B-AWQ")
    ap.add_argument("--granite-url", default="http://localhost:8001/v1")
    ap.add_argument("--laya-device", default="cuda:0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1", help="i/n: run every n-th episode starting at i")
    ap.add_argument("--suites", default="workspace,travel,banking,slack", help="suites to include")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    tasks = load_tasks(a.suites)
    if a.limit:
        tasks = tasks[:a.limit]

    si, sn = map(int, a.shard.split("/"))
    tag = f"{a.system}_{si}of{sn}"
    done = set()
    tp = os.path.join(a.out, f"tasks_{tag}.jsonl")
    if os.path.exists(tp):
        done = {(r["id"], r["run"]) for r in R.jl(tp)}

    jobs = [(e, r) for r in range(a.runs) for e in tasks]
    jobs = [j for k, j in enumerate(jobs) if k % sn == si and (j[0]["id"], j[1]) not in done]
    print(f"{a.system}: {len(jobs)} episodes to run ({len(done)} already done), concurrency {a.concurrency}", flush=True)

    llm = LLM(a.base_url, a.model)
    judge = make_judge(a.system, llm, a)
    sem = asyncio.Semaphore(a.concurrency)
    tf = open(tp, "a")
    lf = open(os.path.join(a.out, f"steps_{tag}.jsonl"), "a")
    t0 = time.time()
    finished = 0

    async def one(e, r):
        nonlocal finished
        async with sem:
            row = await episode(e, r, a.system, llm, judge, lf)
        tf.write(json.dumps(row) + "\n")
        tf.flush()
        finished += 1
        if finished % 10 == 0 or finished == len(jobs):
            print(f"{finished}/{len(jobs)} done, {time.time()-t0:.0f}s", flush=True)

    await asyncio.gather(*(one(e, r) for e, r in jobs))
    print("DONE", a.system, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
