# Accuracy per system with 95% bootstrap CIs over scenarios, plus cost per step and per task.
# usage: python3 analyze.py results_dir [out_prefix]
import glob, json, os, sys
from collections import defaultdict
import numpy as np

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, "summary")
rows = []
for f in sorted(glob.glob(os.path.join(src, "**", "tasks*.jsonl"), recursive=True)):
    rows += [json.loads(l) for l in open(f) if l.strip()]
if not rows:
    sys.exit("no task rows under " + src)

ORDER = ["S1_none", "S2_rules", "S3_llm_judge", "S4a_laya", "S4b_granite"]
systems = [s for s in ORDER if any(r["system"] == s for r in rows)]
systems += sorted({r["system"] for r in rows} - set(systems))
B = 10000
rng = np.random.default_rng(0)


def boot(by_scen):
    # resample scenarios with replacement; a scenario carries all its versions and runs
    keys = sorted(by_scen)
    tot = np.array([len(by_scen[k]) for k in keys], float)
    ok = np.array([sum(by_scen[k]) for k in keys], float)
    idx = rng.integers(0, len(keys), (B, len(keys)))
    acc = ok[idx].sum(1) / tot[idx].sum(1)
    return ok.sum() / tot.sum(), np.percentile(acc, 2.5), np.percentile(acc, 97.5)


summary = {}
for s in systems:
    rs = [r for r in rows if r["system"] == s]
    by_scen = defaultdict(list)
    for r in rs:
        by_scen[r["scenario"]].append(1.0 if r["passed"] else 0.0)
    acc, lo, hi = boot(by_scen)
    steps = sum(r["steps"] for r in rs)
    per_version = {}
    for v in sorted({r["version"] for r in rs}):
        vb = defaultdict(list)
        for r in rs:
            if r["version"] == v:
                vb[r["scenario"]].append(1.0 if r["passed"] else 0.0)
        a, l, h = boot(vb)
        per_version[v] = {"n": sum(len(x) for x in vb.values()), "acc": a, "lo": l, "hi": h}
    summary[s] = {
        "task_runs": len(rs), "scenarios": len(by_scen), "acc": acc, "ci95": [lo, hi],
        "per_version": per_version,
        "empty_turn_fails": sum(r.get("empty_turn_fail", 0) for r in rs),
        "interventions_per_task": float(np.mean([r["interventions"] for r in rs])),
        "asks_per_task": float(np.mean([r.get("asks", 0) for r in rs])),
        "steps_per_task": steps / len(rs),
        "seconds_per_task": float(np.mean([r["seconds"] for r in rs])),
        "seconds_per_step": sum(r["seconds"] for r in rs) / max(steps, 1),
        "agent_tokens_per_task": float(np.mean([r["agent_in"] + r["agent_out"] for r in rs])),
        "judge_tokens_per_task": float(np.mean([r["judge_in"] + r["judge_out"] for r in rs])),
        "tokens_per_step": sum(r["agent_in"] + r["agent_out"] + r["judge_in"] + r["judge_out"] for r in rs) / max(steps, 1),
    }

# paired difference against no judge, same scenarios
if "S1_none" in summary:
    base = defaultdict(list)
    for r in rows:
        if r["system"] == "S1_none":
            base[r["scenario"]].append(1.0 if r["passed"] else 0.0)
    for s in systems:
        if s == "S1_none":
            continue
        cur = defaultdict(list)
        for r in rows:
            if r["system"] == s:
                cur[r["scenario"]].append(1.0 if r["passed"] else 0.0)
        keys = sorted(set(base) & set(cur))
        if not keys:
            continue
        d = np.array([np.mean(cur[k]) - np.mean(base[k]) for k in keys])
        idx = rng.integers(0, len(keys), (B, len(keys)))
        bd = d[idx].mean(1)
        summary[s]["diff_vs_S1"] = [float(d.mean()), float(np.percentile(bd, 2.5)), float(np.percentile(bd, 97.5))]

json.dump(summary, open(out + ".json", "w"), indent=1, default=float)
for s, v in summary.items():
    d = v.get("diff_vs_S1")
    print(f"{s:14s} n={v['task_runs']:5d} acc={v['acc']*100:5.1f} [{v['ci95'][0]*100:5.1f},{v['ci95'][1]*100:5.1f}]"
          f" int/task={v['interventions_per_task']:.2f} s/task={v['seconds_per_task']:.0f}"
          f" tok/task={v['agent_tokens_per_task']+v['judge_tokens_per_task']:.0f}"
          + (f" vsS1={d[0]*100:+.1f} [{d[1]*100:+.1f},{d[2]*100:+.1f}]" if d else ""))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
labels = {"S1_none": "S1 no judge", "S2_rules": "S2 plain rules", "S3_llm_judge": "S3 Qwen3 8B judge",
          "S4a_laya": "S4a Laya as is", "S4b_granite": "S4b Granite Guardian"}
fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=160)
xs = np.arange(len(systems))
acc = np.array([summary[s]["acc"] for s in systems]) * 100
lo = acc - np.array([summary[s]["ci95"][0] for s in systems]) * 100
hi = np.array([summary[s]["ci95"][1] for s in systems]) * 100 - acc
COL = {"S1_none": "#8a8f98", "S2_rules": "#c9a227", "S3_llm_judge": "#3b6fb6", "S4a_laya": "#2e9e6a", "S4b_granite": "#b5523b"}
ax.bar(xs, acc, color=[COL.get(s, "#666") for s in systems], width=0.62)
ax.errorbar(xs, acc, yerr=[lo, hi], fmt="none", ecolor="#222", capsize=5, lw=1.2)
for x, a, s in zip(xs, acc, systems):
    ax.text(x, a + hi[list(systems).index(s)] + 1.2, f"{a:.1f}", ha="center", fontsize=9)
ax.set_xticks(xs, [labels.get(s, s) for s in systems], fontsize=8.5)
AD = all(r["version"] == "agentdojo" for r in rows)
ax.set_ylabel("AgentDojo benign user tasks passed (%)" if AD else "BFCL multi turn tasks passed (%)")
n = summary[systems[0]]
ax.set_title(f"Task accuracy per system, 95% bootstrap CI over {'tasks' if AD else 'scenarios'} ({n['scenarios']} {'tasks' if AD else 'scenarios'})", fontsize=10)
ax.set_ylim(0, max(100, (acc + hi).max() + 8) if (acc + hi).max() > 90 else (acc + hi).max() + 10)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(out + ".png")
print("wrote", out + ".json", out + ".png")
