# run.py with two extra systems, without editing run.py:
#   S1_record          S1 behaviour, every step's judge input saved to <out>/states_<system>.jsonl
#   S4v_<name>         laya variant judge, config from LAYA_CFG (json file holding a list of configs)
#   S_jev              hosted Jev judge (jev_judge.py), config from JEV_CFG
#   S_tree             feature trees judge (tree_judge.py), model from TREE_MODEL
#   S_oracle           reference replay judge (oracle.py), the ceiling for these correction actions
# usage: python laya_run.py <run.py args>
import asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as R
import laya_variants as LV

_episode = R.episode
async def episode(e, run, system, llm, judge, log):
    LV.CUR.set({"id": e["id"], "run": run, "version": e["version"], "scenario": e["scenario"], "gold": e["gold"],
                "e": e, "system": system})
    return await _episode(e, run, system, llm, judge, log)
R.episode = episode

class RecNone(R.NoJudge):
    """Still a NoJudge, so run.py's repeat check stays off exactly as in S1."""
    def __init__(self, path):
        self.rec = LV.Recorder(R.NoJudge(), path)
    async def judge(self, ctx, step):
        return await self.rec.judge(ctx, step)


_make = R.make_judge
def make_judge(system, llm, args):
    out = args.out
    if system == "S1_record":
        return RecNone(os.path.join(out, "states_S1_record.jsonl"))
    if system.startswith("S4v_"):
        cfgs = {c["name"]: c for c in json.load(open(os.environ["LAYA_CFG"]))}
        j = LV.LayaVariantJudge(cfgs[system[4:]], device=getattr(args, "laya_device", "cuda:0"))
        return LV.Recorder(j, os.path.join(out, f"states_{system}.jsonl"))
    if system == "S_oracle":
        import oracle
        return LV.Recorder(oracle.OracleJudge(), os.path.join(out, "states_S_oracle.jsonl"))
    if system == "S_jev":
        import jev_judge
        return LV.Recorder(jev_judge.JevJudge(json.load(open(os.environ["JEV_CFG"]))), os.path.join(out, "states_S_jev.jsonl"))
    if system == "S_layadone":  # finetuned Laya done check (analysis/laya_done_judge.py), used with mode dc
        sys.path.insert(0, os.environ.get("STAY_ANALYSIS", os.path.join(HERE, "..", "..", "analysis")))
        import laya_done_judge
        return LV.Recorder(laya_done_judge.make(), os.path.join(out, "states_S_layadone.jsonl"))
    if system == "S_layastep":  # finetuned Laya step check plus done check (analysis/laya_step_judge.py), used with rb2c
        sys.path.insert(0, os.environ.get("STAY_ANALYSIS", os.path.join(HERE, "..", "..", "analysis")))
        import laya_step_judge
        return LV.Recorder(laya_step_judge.make(), os.path.join(out, "states_S_layastep.jsonl"))
    if system == "S_tree":
        import tree_judge
        return LV.Recorder(tree_judge.TreeJudge(os.environ["TREE_MODEL"]), os.path.join(out, "states_S_tree.jsonl"))
    return _make(system, llm, args)
R.make_judge = make_judge

if __name__ == "__main__":
    asyncio.run(R.main())
