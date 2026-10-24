# Oracle labels and failure types for recorded S1_record runs (Shuban's harness), CPU only.
# Per step: off track by Shuban's rule (endings = suffixes of the turn's reference calls) and by the proposal's rule
# (endings = every order kept subset, up to 8 reference calls), false claim (success words while the state is wrong).
# Per turn: done = end state equals the reference end state and every reference function was called this turn.
# Per failed task: the type of its first failed turn (wrong_step, acted_instead_of_asking, omission_*, step_cap, checker).
# usage: python analysis/oracle_labels.py RUN_DIR [RUN_DIR ...]   (each holds states_*.jsonl and steps_*.jsonl)
# writes RUN_DIR/labels.jsonl, RUN_DIR/turns.jsonl and prints a summary
import glob, itertools, json, os, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = os.path.join(ROOT, "shuban_findings", "code")
os.environ.setdefault("BFCL_LB", os.path.join(ROOT, "third_party", "gorilla", "berkeley-function-call-leaderboard"))
sys.path.insert(0, CODE)
import run as R  # noqa: E402
import oracle  # noqa: E402
import prompts as P  # noqa: E402

E = {e["id"]: e for v in R.VERSIONS for e in R.load_version(v)}
J = oracle.OracleJudge()
MAX_SUBSET = 8


def fname(call):
    return call.split("(", 1)[0].strip()


def endings(gold, subsets):
    if not subsets or len(gold) > MAX_SUBSET:
        return [gold[k:] for k in range(len(gold) + 1)]
    return [[gold[i] for i in idx] for r in range(len(gold) + 1) for idx in itertools.combinations(range(len(gold)), r)]


class Episode:
    """Replays one recorded episode; caches states by number of executed calls."""

    def __init__(self, e, decoded):
        self.e, self.executed = e, [c for turn in decoded for st in turn for c in st]
        self.per_turn = [sum(len(st) for st in turn) for turn in decoded]
        self.cache, self.reach = {}, {}

    def state(self, n):
        if n not in self.cache:
            self.cache[n] = oracle.replay(self.e, self.executed[:n], f"ol{n}")
        return self.cache[n]

    def turn_start(self, t):
        return sum(self.per_turn[:t])

    def target(self, t):
        return J._state_after(self.e, self.state(self.turn_start(t)), list(self.e["gold"][t]))

    def reachable(self, n, t, extra, subsets):
        key = (n, t, tuple(extra), subsets)
        if key not in self.reach:
            base, tgt = self.state(n), self.target_snap(t)
            self.reach[key] = any(J._state_after(self.e, base, list(extra) + end) == tgt
                                  for end in endings(list(self.e["gold"][t]), subsets))
        return self.reach[key]

    def target_snap(self, t):
        k = ("target", t)
        if k not in self.cache:
            self.cache[k] = self.target(t)
        return self.cache[k]


def label_dir(d):
    dec = {}
    for f in glob.glob(os.path.join(d, "steps_*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            dec[(r["id"], r["run"])] = r["decoded"]
    tasks = {}
    for f in glob.glob(os.path.join(d, "tasks_*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            tasks[(r["id"], r["run"])] = r
    recs = defaultdict(list)
    for f in glob.glob(os.path.join(d, "states_*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            recs[(r["id"], r["run"])].append(r)
    lab_f, turn_f = open(os.path.join(d, "labels.jsonl"), "w"), open(os.path.join(d, "turns.jsonl"), "w")
    fail_types, step_counts, done_counts = Counter(), Counter(), Counter()
    for key, rs in sorted(recs.items()):
        if key not in dec or key not in tasks:
            continue  # episode still running or cut by the job end
        e, task = E[key[0]], tasks[key]
        ep = Episode(e, dec[key])
        turns = defaultdict(list)
        for k, r in enumerate(rs):
            if r["turn"] < len(dec[key]):
                turns[r["turn"]].append((k, r))
        turn_rows = []
        for t in range(len(dec[key])):
            start, end = ep.turn_start(t), ep.turn_start(t) + ep.per_turn[t]
            tgt = ep.target_snap(t)
            called = {fname(c) for st in dec[key][t] for c in st}
            missing = sorted({fname(g) for g in e["gold"][t]} - called)
            state_ok = R.snapshot(ep.state(end)) == tgt
            done = state_ok and not missing
            rows = turns.get(t, [])
            last_msg = max((k for k, r in rows if r["step"]["kind"] == "msg"), default=None)
            flagged_sfx = flagged_sub = 0
            for k, r in rows:
                n, step = r["n_recent"], r["step"]
                out = {"id": key[0], "run": key[1], "k": k, "turn": t, "kind": step["kind"], "version": r["version"],
                       "scenario": r["scenario"]}
                if step["kind"] == "msg":
                    out["false_claim"] = int(bool(P.SUCCESS_WORDS.search(step["text"])) and R.snapshot(ep.state(n)) != tgt)
                    out["turn_end"] = int(k == last_msg)
                    if k == last_msg:
                        out["done"] = int(done)
                else:
                    for subsets, name in ((False, "off_track_suffix"), (True, "off_track_subset")):
                        before = ep.reachable(n, t, [], subsets)
                        out[name] = int(before and not ep.reachable(n, t, [step["text"]], subsets))
                    flagged_sfx += out["off_track_suffix"]; flagged_sub += out["off_track_subset"]
                lab_f.write(json.dumps(out) + "\n")
                for c in ("false_claim", "off_track_suffix", "off_track_subset", "done"):
                    if c in out:
                        step_counts[(step["kind"], c, out[c])] += 1
            last_text = rows[-1][1]["step"].get("text", "") if rows and rows[-1][1]["step"]["kind"] == "msg" else ""
            if done:
                ftype = None
            elif not e["gold"][t]:
                ftype = "acted_instead_of_asking" if flagged_sub else "other_empty_turn"
            elif flagged_sub:
                ftype = "wrong_step"
            elif not last_text:
                ftype = "step_cap"
            elif last_text.rstrip().endswith("?"):
                ftype = "omission_asked_user"
            elif P.SUCCESS_WORDS.search(last_text):
                ftype = "omission_claimed_done"
            else:
                ftype = "omission_stopped"
            row = {"id": key[0], "run": key[1], "turn": t, "version": e["version"], "scenario": e["scenario"], "done": int(done),
                   "state_ok": int(state_ok), "missing": missing, "flagged_suffix": flagged_sfx, "flagged_subset": flagged_sub,
                   "failure": ftype, "gold_empty": int(not e["gold"][t])}
            turn_f.write(json.dumps(row) + "\n")
            turn_rows.append(row)
            done_counts[int(done)] += 1
        if not task["passed"]:
            first = next((r for r in turn_rows if not r["done"]), None)
            if first is None:
                ftype = "step_cap" if len(dec[key]) < len(e["question"]) else "checker_only"
            else:
                ftype = first["failure"]
            fail_types[ftype] += 1
    lab_f.close(); turn_f.close()
    return fail_types, step_counts, done_counts, tasks


def main():
    for d in sys.argv[1:]:
        fail_types, steps, done, tasks = label_dir(d)
        n, p = len(tasks), sum(t["passed"] for t in tasks.values())
        print(f"== {d}: {n} tasks, {p} passed ({100 * p / max(n, 1):.1f}%)")
        tot = sum(fail_types.values())
        print(f"  failed tasks by type of their first failed turn ({tot}):")
        for k, v in fail_types.most_common():
            print(f"    {k:26s} {v:4d}  {100 * v / tot:5.1f}%")
        print(f"  turns done {done[1]}, not done {done[0]}")
        for kind, c in (("call", "off_track_suffix"), ("call", "off_track_subset"), ("msg", "false_claim"), ("msg", "done")):
            a, b = steps[(kind, c, 1)], steps[(kind, c, 0)]
            print(f"  {kind:4s} {c:18s} 1: {a:5d}  0: {b:5d}  ({100 * a / max(a + b, 1):.1f}% positive)")


if __name__ == "__main__":
    main()
