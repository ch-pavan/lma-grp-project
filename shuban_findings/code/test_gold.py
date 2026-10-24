# Plumbing check without a GPU: a mock LLM replays each turn's gold calls, so every kept task must pass.
# usage: python test_gold.py [versions] [n_scenarios] [system]
import ast, asyncio, io, json, sys, types
import run as R

versions = (sys.argv[1] if len(sys.argv) > 1 else "base,miss_param,miss_func,long_context").split(",")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
SYSTEM = sys.argv[3] if len(sys.argv) > 3 else "S1_none"


def parse_call(s, docs):
    node = ast.parse(s, mode="eval").body
    name = node.func.id
    args = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
    if node.args:
        doc = next(d for d in docs if d["name"] == name)
        order = list(doc["parameters"]["properties"])
        for i, a in enumerate(node.args):
            args[order[i]] = ast.literal_eval(a)
    return name, args


class Mock:
    def __init__(self, e):
        self.e = e
        self.docs = [d for c in e["involved_classes"] for d in R.docs_for(c)]
        self.turn = -1
        self.sent = False

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=0, temperature=None):
        if tool_choice == "none":  # planner call starts a new turn
            self.turn += 1
            self.sent = False
            names = [parse_call(c, self.docs)[0] for c in self.e["gold"][self.turn]]
            return types.SimpleNamespace(content="1. " + ", ".join(names), tool_calls=None), 10, 5
        if think:  # LLM judge: always pass
            return types.SimpleNamespace(content="VERDICT Q1=on_track Q2=none", tool_calls=None), 10, 5
        gold = self.e["gold"][self.turn]
        if self.sent or not gold:
            self.sent = True
            return types.SimpleNamespace(content=("Done." if gold else "Which value should I use? Please provide it."), tool_calls=None), 10, 2
        self.sent = True
        tcs = []
        for i, c in enumerate(gold):
            n, a = parse_call(c, self.docs)
            tcs.append(types.SimpleNamespace(id=f"c{i}", function=types.SimpleNamespace(name=n, arguments=json.dumps(a))))
        return types.SimpleNamespace(content=None, tool_calls=tcs), 10, 5


AUD = __import__("collections").Counter()
class Audit:
    """Records what the judge would say on each gold step but lets every step through."""
    def __init__(self, j): self.j = j
    async def judge(self, ctx, step):
        v = await self.j.judge(ctx, step)
        AUD[step["kind"]] += 1
        if v["q1"] != "on_track" or v["q2"] != "none":
            AUD[(step["kind"], v["q1"], v["q2"])] += 1
            if len(EX) < 12: EX.append((step["text"][:90], [w for _, _, w in step["ev"]]))
        return {**v, "q1": "on_track", "q2": "none"}
EX = []
LOG = open(__import__("os").environ.get("GOLD_LOG", "gold_steps.jsonl"), "w")

async def main():
    keep = set(range(200)) - R.UNSOUND
    rows = []
    judge_args = types.SimpleNamespace()
    for v in versions:
        for e in R.load_version(v):
            if e["scenario"] not in keep or e["scenario"] >= N:
                continue
            m = Mock(e)
            judge = Audit(R.make_judge(SYSTEM, m, judge_args))
            rows.append(await R.episode(e, 0, SYSTEM, m, judge, LOG))
    for v in versions:
        rs = [r for r in rows if r["version"] == v]
        bad = [(r["id"], r["error_type"], r["harness_error"]) for r in rs if not r["passed"]]
        print(v, f"{sum(r['passed'] for r in rs)}/{len(rs)} passed, interventions {sum(r['interventions'] for r in rs)}, asks {sum(r['asks'] for r in rs)}", bad[:5])

asyncio.run(main())
print("gold false flags:", dict(AUD)); [print(" ", x) for x in EX]
