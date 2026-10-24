# Plumbing check for actions.py without a GPU: a gold replaying doer under judges that flag the first try, or every try.
# Every kept task must still pass, since a flag may cost resamples or a fallback but never a stall.
# usage: python test_actions.py bfcl [n_scenarios]   |   .venv-agentdojo/bin/python test_actions.py agentdojo
import ast, asyncio, json, math, sys, types
from collections import Counter
import actions as A
import run as R


def parse_call(s, docs):  # same as test_gold.parse_call; that module runs on import
    node = ast.parse(s, mode="eval").body
    args = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
    if node.args:
        order = list(next(d for d in docs if d["name"] == node.func.id)["parameters"]["properties"])
        for i, a in enumerate(node.args):
            args[order[i]] = ast.literal_eval(a)
    return node.func.id, args

NS = types.SimpleNamespace


def msg(content=None, calls=None):
    return NS(content=content, tool_calls=[NS(id=f"c{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(calls)] if calls else None)


def tail(messages):
    return [m for m in messages if not (m["role"] == "user" and m["content"] == A.HINT)]


class BfclMock:
    """Stateless: proposes the turn's gold calls unless the context already ends with tool outputs, then closes."""
    def __init__(self, e):
        self.e, self.turn = e, -1
        self.docs = [d for c in e["involved_classes"] for d in R.docs_for(c)]

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=0, temperature=None):
        self.turn += 1  # only the planner calls chat here
        return NS(content="plan", tool_calls=None), 10, 5

    async def sample(self, messages, tools, n=1):
        gold = self.e["gold"][self.turn]
        ms = tail(messages)
        last_user = max(i for i, m in enumerate(ms) if m["role"] == "user")
        k = sum(len(m.get("tool_calls") or []) for m in ms[last_user:] if m["role"] == "assistant")
        if k >= len(gold):
            m = msg("Done." if gold else "Which value should I use? Please provide it.")
        else:
            m = msg(calls=[parse_call(c, self.docs) for c in gold[k:]])
        return [m] * n, 10, 5


class AdMock:
    def __init__(self, e):
        self.task = e["task"]
        self.gt = self.task.ground_truth(self.task.init_environment(e["suite_obj"].load_and_inject_default_environment({})))

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=0, temperature=None):
        return NS(content="plan", tool_calls=None), 10, 5

    async def sample(self, messages, tools, n=1):
        k = sum(1 for m in tail(messages) if m["role"] == "assistant" and m.get("tool_calls"))
        if k < len(self.gt):
            m = msg(calls=[(self.gt[k].function, self.gt[k].args)])
        else:
            m = msg(getattr(self.task, "GROUND_TRUTH_OUTPUT", "") or "Done.")
        return [m] * n, 10, 5


class FlagJudge:
    """Flags a step the first time it is seen (first=True) or always."""
    def __init__(self, always):
        self.always, self.seen = always, set()

    async def judge(self, ctx, step):
        key = (id(ctx["requests"]), len(ctx["requests"]), step["text"])
        flag = self.always or key not in self.seen
        self.seen.add(key)
        return R.Verdict(q1="off_track" if flag else "on_track", q2="none", q3="needed", jin=0, jout=0)


def test_pflag():
    T = lambda tok, alts: NS(token=tok, logprob=0.0, top_logprobs=[NS(token=a, logprob=math.log(p)) for a, p in alts])
    toks = [T("VER", [("VER", 1)]), T("DICT", [("DICT", 1)]), T(" Q1=", [(" Q1=", 1)]), T("off", [("off", .7), ("on", .3)]),
            T("_track", [("_track", 1)]), T(" Q2=", [(" Q2=", 1)]), T("none", [("none", .9), ("made", .1)])]
    p = A.p_flag({"q1": "off_track", "q2": "none"}, toks)
    assert abs(p - (1 - .3 * .9)) < 1e-6, p
    print("p_flag ok", round(p, 3))


async def main():
    bench = sys.argv[1] if len(sys.argv) > 1 else "bfcl"
    if bench == "bfcl":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        keep = set(range(200)) - R.UNSOUND
        es = [e for v in R.VERSIONS for e in R.load_version(v) if e["scenario"] in keep and e["scenario"] < n]
        run_ep, Mock = A.bfcl_episode, BfclMock
    else:
        import agentdojo_run as AD
        es = AD.load_tasks()
        run_ep, Mock = A.ad_episode, AdMock
    log = open("/dev/null", "w")
    for system, always in [("X@rb2", False), ("X@rbh2d", False), ("X@rb2", True), ("X@vote3", True), ("X@rank3", True)]:
        _, mode = A.parse_system(system)
        rows = []
        for e in es:
            rows.append(await run_ep(e, 0, system, Mock(e), FlagJudge(always), log, mode))
        c = Counter()
        for r in rows:
            for k in ("passed", "steps", "interventions", "resamples", "fallbacks", "vote_skips"):
                c[k] += r[k]
        bad = [(r["id"], r["error_type"], r["harness_error"]) for r in rows if not r["passed"]]
        print(f"{bench} {system} always_flag={always}: {c['passed']}/{len(rows)} passed", dict(c), bad[:4], flush=True)


if __name__ == "__main__":
    test_pflag()
    asyncio.run(main())
