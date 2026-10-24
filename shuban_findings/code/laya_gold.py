# Judge inputs for known good steps: replay every gold call of the train and val scenarios through the harness
# (mock LLM, no GPU) and save each step's judge input. usage: python laya_gold.py OUT.jsonl [splits]
import asyncio, ast, json, sys, types
import run as R
import laya_variants as LV



def parse_call(s, docs):
    node = ast.parse(s, mode="eval").body
    args = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
    if node.args:
        order = list(next(d for d in docs if d["name"] == node.func.id)["parameters"]["properties"])
        for i, a in enumerate(node.args):
            args[order[i]] = ast.literal_eval(a)
    return node.func.id, args


class Mock:
    """Planner lists the turn's gold tool names, doer sends the gold calls then closes."""
    def __init__(self, e):
        self.e, self.turn, self.sent = e, -1, False
        self.docs = [d for c in e["involved_classes"] for d in R.docs_for(c)]

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=0, temperature=None):
        if tool_choice == "none":
            self.turn += 1
            self.sent = False
            names = [parse_call(c, self.docs)[0] for c in self.e["gold"][self.turn]]
            return types.SimpleNamespace(content="1. " + ", ".join(names) if names else "Ask the user for the missing value.", tool_calls=None), 10, 5
        gold = self.e["gold"][self.turn]
        if self.sent or not gold:
            self.sent = True
            return types.SimpleNamespace(content=("Done." if gold else "Which value should I use? Please provide it."), tool_calls=None), 10, 2
        self.sent = True
        tcs = [types.SimpleNamespace(id=f"c{i}", function=types.SimpleNamespace(name=n, arguments=json.dumps(a)))
               for i, (n, a) in enumerate(parse_call(c, self.docs) for c in gold)]
        return types.SimpleNamespace(content=None, tool_calls=tcs), 10, 5


class RecNone(R.NoJudge):
    def __init__(self, path):
        self.rec = LV.Recorder(R.NoJudge(), path)
    async def judge(self, ctx, step):
        return await self.rec.judge(ctx, step)


async def main(OUT, SPLITS):
    sp = R.split()
    keep = {s for k in SPLITS for s in sp[k]}
    judge = RecNone(OUT)
    log = open("/dev/null", "w")
    n = ok = 0
    for v in R.VERSIONS:
        for e in R.load_version(v):
            if e["scenario"] not in keep:
                continue
            LV.CUR.set({"id": e["id"], "run": 0, "version": v, "scenario": e["scenario"], "gold": e["gold"]})
            row = await R.episode(e, 0, "gold", Mock(e), judge, log)
            n += 1; ok += row["passed"]
    print(f"gold replay {ok}/{n} passed, states in {OUT}")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "train,val").split(",")))
