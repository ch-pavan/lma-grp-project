# Results of job 49671 and its follow-ups (49688 offline, 49719 Laya rerun, 49710 and 49764 the 9B judge live in two
# shards). Live: pass rate on the 120 val tasks against no judge (job 49274), with a 95% CI from a paired bootstrap over
# scenarios, and tasks gained or lost. Offline: the 9B as SLM judge (annotate.py, guide v1) and the finetuned Laya step
# head (job 49656) on the same 1,277 val calls, scored against the step labels of build_step_data.py.
# usage: python analysis/rb_results.py   (reads runs/data/, which is not in git)
import collections, glob, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_laya_done as T  # noqa: E402

D = "runs/data/"
R = D + "q9b_rb_49671/"


def load(p):
    return {(r["id"], r["run"]): r for f in glob.glob(p) for r in map(json.loads, open(f))}


def live():
    base = load(D + "q9b_dc_49274/S1_none/tasks_*.jsonl")
    systems = {"no judge (49274)": base, "no judge, rerun (49146)": load(D + "q9b_s1t_49146/val/tasks_*.jsonl"),
               "done check only (49274)": load(D + "q9b_dc_49274/S_layadone*/tasks_*.jsonl"),
               "Laya step+done, gate bug (49671)": load(R + "S_layastep@rbh2dc/tasks_*.jsonl"),
               "Laya step+done, fixed (49719)": load(R + "S_layastep@rbh2dc_fix/tasks_*.jsonl"),
               "9B judge (49710, 49764)": load(R + "S3_llm_judge@rbh2dc/tasks_*.jsonl"),
               "oracle (49671)": load(R + "S_oracle@rbh2dc/tasks_*.jsonl")}
    rng = np.random.default_rng(0)
    for name, d in systems.items():
        keys = sorted(set(d) & set(base))
        by = collections.defaultdict(list)
        for k in keys:
            by[d[k]["scenario"]].append(k)
        sc = sorted(by)
        diff = np.array([sum(d[k]["passed"] - base[k]["passed"] for k in by[s]) for s in sc], float)
        cnt = np.array([len(by[s]) for s in sc], float)
        idx = rng.integers(0, len(sc), (10000, len(sc)))
        bs = diff[idx].sum(1) / cnt[idx].sum(1) * 100
        m = lambda f: np.mean([d[k].get(f) or 0 for k in keys])  # noqa: E731
        won = sum(d[k]["passed"] and not base[k]["passed"] for k in keys)
        lost = sum(base[k]["passed"] and not d[k]["passed"] for k in keys)
        print(f"{name:34s} n={len(keys)} pass {np.mean([d[k]['passed'] for k in keys]) * 100:5.1f}%  "
              f"{diff.sum() / cnt.sum() * 100:+5.1f} [{np.percentile(bs, 2.5):+.1f}, {np.percentile(bs, 97.5):+.1f}]  "
              f"+{won} -{lost}  steps {m('steps'):.1f} interventions {m('interventions'):.2f} resamples {m('resamples'):.2f}")


def offline():
    rows = [json.loads(l) for l in open(D + "laya_step/val.jsonl") if '"q35_9b:val|' in l]
    sc = {r["uid"]: r["p_not_done"] for r in map(json.loads, open(D + "laya_runs/49656/val_scores.jsonl"))}
    thr = json.load(open(D + "laya_runs/49656/results.json"))["best"]["dev"]["threshold"]
    # Both list an episode's calls in order: Laya rows by pooled index, annotate.py rows by state index.
    L, O = collections.defaultdict(list), collections.defaultdict(list)
    for r in rows:
        _, i, run, g = r["uid"].split("|")
        L[(i, run)].append((int(g), r))
    for r in map(json.loads, open(R + "offline_9b_steps.jsonl")):
        i, run, k, _ = r["uid"].split("|")
        O[(i, run)].append((int(k), r))
    pairs = []
    for key in L:
        a, b = sorted(L[key], key=lambda x: x[0]), sorted(O[key], key=lambda x: x[0])
        assert len(a) == len(b), key
        pairs += [(x[1], y[1]) for x, y in zip(a, b)]
    y = [1 - l["label"] for l, _ in pairs]
    laya = [sc[l["uid"]] for l, _ in pairs]
    nine = [j["q1"] == "off_track" or j["q2"] not in (None, "none") for _, j in pairs]
    print(f"val calls {len(y)}, bad {sum(y)}, 9B parse fails {sum(j['q1'] is None for _, j in pairs)} (count as not flagged)")
    k = sum(nine)
    for name, pred in (("9B judge (Q1 off track or Q2 flag)", nine), (f"Laya, dev threshold {thr:.3f}", [x >= thr for x in laya]),
                       (f"Laya, top {k} (9B's flag count)", [x >= sorted(laya, reverse=True)[k - 1] for x in laya])):
        p, r, f = T.prf(y, pred)[:3]
        print(f"  {name:38s} flags {sum(pred):4d}  precision {p:.2f} recall {r:.2f} F1 {f:.2f}")
    print(f"  AUROC: Laya {T.auroc(y, laya):.3f}, 9B (yes/no) {T.auroc(y, [int(x) for x in nine]):.3f}")
    print(f"  9B cost per call: {np.mean([j['out'] for _, j in pairs]):.0f} output tokens, {np.mean([j['seconds'] for _, j in pairs]):.0f} s at 96 at once")


if __name__ == "__main__":
    live()
    print()
    offline()
