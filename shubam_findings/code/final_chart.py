# Final chart: pass rate with 95% CI per system, BFCL test and AgentDojo side by side, grouped by agent model.
# usage: python3 final_chart.py BFCL_TABLE.json AD_TABLE.json OUT.png   (tables from actions_table.py)
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAMES = {"S1_none": "no judge", "S3_llm_judge@dc": "LLM done check", "S_oracle@rbh2dc": "oracle ceiling"}
COLORS = {"S1_none": "#8a8f98", "S3_llm_judge@dc": "#3b6fb6", "S_oracle@rbh2dc": "#2e9e6a"}
MODELS = {"": "Qwen3 8B", "q35": "Qwen3.5 4B", "q359b": "Qwen3.5 9B"}


def split(label):
    base, _, suf = label.partition("__")
    return base, suf


fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), dpi=160, sharey=True)
for ax, path, title in zip(axes, sys.argv[1:3], ["BFCL multi turn, test", "AgentDojo benign"]):
    T = json.load(open(path))
    models = list(dict.fromkeys(split(s)[1] for s in T))
    systems = [s for s in NAMES if any(split(x)[0] == s for x in T)]
    w = 0.8 / len(systems)
    for mi, m in enumerate(models):
        for si, s in enumerate(systems):
            v = T.get(s + ("__" + m if m else ""))
            if not v:
                continue
            x = mi + (si - (len(systems) - 1) / 2) * w
            a, lo, hi = v["acc"] * 100, v["ci95"][0] * 100, v["ci95"][1] * 100
            ax.bar(x, a, w * 0.9, color=COLORS[s], label=NAMES[s] if mi == 0 else None)
            ax.errorbar(x, a, yerr=[[a - lo], [hi - a]], fmt="none", ecolor="#222", capsize=4, lw=1)
            ax.text(x, hi + 1, f"{a:.0f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(models)), [MODELS.get(m, m) for m in models])
    ax.set_title(title, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("tasks passed (%)")
axes[0].legend(frameon=False, fontsize=8, loc="upper left")
axes[0].set_ylim(0, 100)
fig.suptitle("Pass rate per system with 95% bootstrap CI over scenarios", fontsize=10)
fig.tight_layout()
fig.savefig(sys.argv[3])
print("wrote", sys.argv[3])
