# Step judge trained from scratch on hand built features (no language model). Fitting: hand_clf.py.
# Prediction runs from an exported JSON of the boosted trees, so no sklearn is needed at run time.
import json, math
import prompts as P
import run as R
import laya_variants as LV

WHERE = ["request", "tool output", "tool docs", "environment", "composed", "arithmetic", "nowhere"]
NAMES = ["is_msg", "n_args"] + [f"ev_{w.replace(' ', '_')}" for w in WHERE] + [
    "in_plan", "irreversible", "exact_repeat", "repeat_of_error", "k_turn", "n_recent", "success_words", "asks_question",
    "last_error", "msg_len"]


def featurize(step, plan, recent, k_turn, n_recent):
    ev = [w for *_, w in (step.get("ev") or [])]
    text = step.get("text") or ""
    prev = {c: str(o) for c, o in recent}
    last = str(recent[-1][1]) if recent else ""
    is_call = step["kind"] == "call"
    name = step.get("name") or ""
    return [0.0 if is_call else 1.0, float(len(step.get("args") or {}))] + [float(ev.count(w)) for w in WHERE] + [
        float(is_call and name in (plan or "")), float(name in R.IRREVERSIBLE), float(is_call and text in prev),
        float(is_call and prev.get(text, "").lower().startswith("error")), float(k_turn), float(n_recent),
        float(not is_call and bool(P.SUCCESS_WORDS.search(text))), float(not is_call and "?" in text),
        float("error" in last.lower()), float(0 if is_call else len(text))]


def tree_predict(model, x):
    z = model["baseline"]
    for nodes in model["trees"]:
        i = 0
        while not nodes[i]["leaf"]:
            n = nodes[i]
            i = n["left"] if x[n["f"]] <= n["thr"] else n["right"]
        z += nodes[i]["value"]
    return z


class TreeJudge:
    """Flags q1 off_track on calls and q2 false_claim on closing messages when the tree score passes the threshold."""
    name = "S_tree"

    def __init__(self, path):
        self.m = json.load(open(path))
        self.k = {}

    async def judge(self, ctx, step):
        cur = LV.CUR.get() or {}
        tk = (cur.get("id"), cur.get("run"), len(ctx["requests"]) - 1)
        k = self.k.get(tk, 0)
        self.k[tk] = k + 1
        x = featurize(step, ctx["plan"], [tuple(r) for r in ctx["recent"][-4:]], k, len(ctx["recent"]))
        z = tree_predict(self.m, x)
        out = {"q1": "on_track", "q2": "none", "q3": "needed", "score": round(z, 3), "jin": 0, "jout": 0}
        if z > self.m["t"][step["kind"]]:
            out["q1" if step["kind"] == "call" else "q2"] = "off_track" if step["kind"] == "call" else "false_claim"
        return out
