# Table of systems and correction modes: accuracy with 95% bootstrap CI over scenarios, paired difference against the
# no judge baseline, flags, resamples, fallbacks, step cap hits, tokens and seconds per task. Optional bar chart.
# usage: python3 actions_table.py OUT_PREFIX DIR [DIR ...]   (every tasks*.jsonl under the dirs; S1_record counts as S1)
import glob, json, os, sys
from collections import defaultdict
import numpy as np

out, dirs = sys.argv[1], sys.argv[2:]
rows = []
for d in dirs:
    for f in sorted(glob.glob(os.path.join(d, "**", "tasks*.jsonl"), recursive=True)):
        tag = os.path.basename(os.path.dirname(f))  # result folder name, so the same system under two models stays apart
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                r["label"] = tag
                rows.append(r)
B, rng = 10000, np.random.default_rng(0)
labels = list(dict.fromkeys(r["label"] for r in rows))
base_label = next((s for s in labels if s in ("S1_none", "S1_record")), None)  # plain S1, never S1 with a mode


def by_scen(rs):
    b = defaultdict(list)
    for r in rs:
        b[r["scenario"]].append(1.0 if r["passed"] else 0.0)
    return b


def boot(b):
    keys = sorted(b)
    tot = np.array([len(b[k]) for k in keys], float)
    ok = np.array([sum(b[k]) for k in keys], float)
    idx = rng.integers(0, len(keys), (B, len(keys)))
    acc = ok[idx].sum(1) / tot[idx].sum(1)
    return ok.sum() / tot.sum(), np.percentile(acc, 2.5), np.percentile(acc, 97.5)


S = {}
for s in labels:
    rs = [r for r in rows if r["label"] == s]
    b = by_scen(rs)
    acc, lo, hi = boot(b)
    m = lambda k: float(np.mean([r.get(k, 0) for r in rs]))
    v = {"system": rs[0]["system"], "n": len(rs), "scenarios": len(b), "acc": acc, "ci95": [lo, hi],
         "flags_per_task": m("interventions"), "resamples_per_task": m("resamples"), "fallbacks_per_task": m("fallbacks"),
         "fresh_doers_per_task": m("fresh_doers"), "vote_skips_per_task": m("vote_skips"), "deep_per_task": m("deep_rollbacks"),
         "steps_per_task": m("steps"), "step_cap_hits": sum(r["error_type"] == "harness:forced_quit" for r in rs),
         "harness_errors": sum(bool(r.get("harness_error")) for r in rs),
         "agent_tok": float(np.mean([r["agent_in"] + r["agent_out"] for r in rs])),
         "judge_tok": float(np.mean([r["judge_in"] + r["judge_out"] for r in rs])), "seconds": m("seconds")}
    bl = base_label
    if "__" in s:  # rows run with another agent model (folder suffix) pair against that model's own S1
        bl = next((x for x in labels if x.startswith("S1_none__") and x.split("__")[1] == s.split("__")[1]), None)
    base = by_scen([r for r in rows if r["label"] == bl]) if bl else {}
    keys = sorted(set(base) & set(b))
    if bl and s != bl and keys:
        d = np.array([np.mean(b[k]) - np.mean(base[k]) for k in keys])
        bd = d[rng.integers(0, len(keys), (B, len(keys)))].mean(1)
        v["diff_vs_S1"] = [float(d.mean()), float(np.percentile(bd, 2.5)), float(np.percentile(bd, 97.5))]
    S[s] = v
json.dump(S, open(out + ".json", "w"), indent=1, default=float)

hdr = "| system | n | passed % [95% CI] | vs S1 (paired) | flags/task | resamples/task | fallbacks/task | step cap hits | k tokens/task (agent+judge) | s/task |"
lines = [hdr, "|" + "|".join(["---"] * (hdr.count("|") - 1)) + "|"]
for s, v in S.items():
    d = v.get("diff_vs_S1")
    lines.append(f"| {s} | {v['n']} | {v['acc']*100:.1f} [{v['ci95'][0]*100:.1f}, {v['ci95'][1]*100:.1f}] | "
                 + (f"{d[0]*100:+.1f} [{d[1]*100:+.1f}, {d[2]*100:+.1f}]" if d else "") +
                 f" | {v['flags_per_task']:.2f} | {v['resamples_per_task']:.2f} | {v['fallbacks_per_task']:.2f} | {v['step_cap_hits']} | "
                 f"{(v['agent_tok']+v['judge_tok'])/1000:.0f} ({v['agent_tok']/1000:.0f}+{v['judge_tok']/1000:.0f}) | {v['seconds']:.0f} |")
open(out + ".md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))

if os.environ.get("CHART"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ss = list(S)
    acc = np.array([S[s]["acc"] for s in ss]) * 100
    lo = acc - np.array([S[s]["ci95"][0] for s in ss]) * 100
    hi = np.array([S[s]["ci95"][1] for s in ss]) * 100 - acc
    fig, ax = plt.subplots(figsize=(1.3 * len(ss) + 2.5, 4.2), dpi=160)
    xs = np.arange(len(ss))
    ax.bar(xs, acc, width=0.62, color=["#8a8f98" if s == base_label else "#3b6fb6" if "@" not in S[s]["system"] else "#2e9e6a" for s in ss])
    ax.errorbar(xs, acc, yerr=[lo, hi], fmt="none", ecolor="#222", capsize=5, lw=1.2)
    for x, a, h in zip(xs, acc, hi):
        ax.text(x, a + h + 1.0, f"{a:.1f}", ha="center", fontsize=9)
    ax.set_xticks(xs, [s.replace("_llm_judge", "").replace("@", "\n") for s in ss], fontsize=8)
    ax.set_ylabel(os.environ.get("YLABEL", "tasks passed (%)"))
    ax.set_title(os.environ.get("TITLE", "Accuracy per system, 95% bootstrap CI over scenarios"), fontsize=10)
    ax.set_ylim(0, (acc + hi).max() + 10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out + ".png")
    print("wrote", out + ".png")
