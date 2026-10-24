# Oracle step judge, the ceiling for any judge with the same correction actions. It reads the reference calls:
# a call is off track when, before it, some ending of the turn's reference calls still reaches the turn's
# reference end state and, after it, none does. A closing message is a false claim when it reports success
# while the turn's state differs from that reference end state. State only; BFCL's response check is not modelled.
import copy, re
import run as R
import prompts as P
import laya_variants as LV

U = R.U


def key(model_name, test_id, cls):
    return re.sub(r"[-./:]", "_", f"{model_name}_{test_id}_{cls}_instance")


class OracleJudge:
    name = "S_oracle"

    def __init__(self):
        self.turn_start = {}  # (id, run, turn) -> deep copies of the instances when the turn's first step was judged
        self.n = 0

    def _live(self, e, model_name):
        return {c: vars(U)[key(model_name, e["id"], c)] for c in e["involved_classes"]}

    def _state_after(self, e, base, calls):
        """Snapshot after running calls on a copy of base (dict class -> instance)."""
        self.n += 1
        sim = f"oraclesim{self.n}"
        for c, o in base.items():
            vars(U)[key(sim, e["id"], c)] = copy.deepcopy(o)
        if calls:
            U.execute_multi_turn_func_call(calls, e["initial_config"], e["involved_classes"], sim, e["id"],
                                           long_context=e["version"] == "long_context")
        snap = R.snapshot({c: vars(U)[key(sim, e["id"], c)] for c in base})
        for c in base:
            del vars(U)[key(sim, e["id"], c)]
        return snap

    def _reachable(self, e, base, prefix, gold, target):
        return any(self._state_after(e, base, prefix + gold[k:]) == target for k in range(len(gold) + 1))

    async def judge(self, ctx, step):
        cur = LV.CUR.get()
        e, run, t = cur["e"], cur["run"], len(ctx["requests"]) - 1
        model_name = f"{cur['system']}_r{run}"
        live = self._live(e, model_name)
        tk = (e["id"], run, t)
        if tk not in self.turn_start:
            self.turn_start[tk] = {c: copy.deepcopy(o) for c, o in live.items()}
        gold = list(e["gold"][t])
        target = self._state_after(e, self.turn_start[tk], gold)
        ok = {"q1": "on_track", "q2": "none", "q3": "needed", "jin": 0, "jout": 0}
        if step["kind"] == "msg":
            if P.SUCCESS_WORDS.search(step["text"]) and R.snapshot(live) != target:
                return {**ok, "q2": "false_claim"}
            return ok
        if not self._reachable(e, live, [], gold, target):
            return ok  # already lost before this call: nothing left to protect
        if self._reachable(e, live, [step["text"]], gold, target):
            return ok
        return {**ok, "q1": "off_track"}


def replay(e, calls, tag):
    """Fresh instances for e after running calls from the initial config (scratch model name, removed after)."""
    lc = e["version"] == "long_context"
    _, inst = U.execute_multi_turn_func_call(list(calls), e["initial_config"], e["involved_classes"], tag, e["id"], long_context=lc)
    R.reset_instances(tag, e["id"])
    return inst


def offline_label(j, e, executed, n_before, n_turn_start, t, step):
    """Oracle verdict (1 flag, 0 pass) for a recorded step, rebuilding the state by replaying executed calls."""
    gold = list(e["gold"][t])
    start = replay(e, executed[:n_turn_start], "orl_start")
    target = j._state_after(e, start, gold)
    now = replay(e, executed[:n_before], "orl_now")
    if step["kind"] == "msg":
        return int(bool(P.SUCCESS_WORDS.search(step["text"])) and R.snapshot(now) != target)
    if not j._reachable(e, now, [], gold, target):
        return 0
    return int(not j._reachable(e, now, [step["text"]], gold, target))
