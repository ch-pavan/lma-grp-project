import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
BLUE, LBLUE = "#2F5D8A", "#DCE8F4"
ORG, LORG = "#C8651B", "#F9E3D2"
GREY, LGREY = "#555555", "#EEEEEE"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.spines.top": False, "axes.spines.right": False})


def box(ax, x, y, w, h, text, fc=LGREY, ec=GREY, bold=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=0.9))
    ax.text(x, y, text, ha="center", va="center", fontsize=7.2, fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, p, q, text=None, tpos=None, rad=0.0, color=GREY, ha="center"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, lw=0.9, color=color, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
    if text:
        ax.text(*tpos, text, fontsize=6.6, color=color, ha=ha, va="center", style="italic")


def fig_system():
    fig, ax = plt.subplots(figsize=(6.7, 3.15))
    ax.set_xlim(0, 6.7); ax.set_ylim(0, 3.15); ax.axis("off")
    yt, ym, yb = 2.65, 1.65, 0.62
    box(ax, 0.62, yt, 1.0, 0.5, "User request\n(one turn)")
    box(ax, 1.86, yt, 1.0, 0.5, "Planner\nwrites a plan")
    box(ax, 3.1, yt, 1.0, 0.5, "Doer\nproposes a call")
    box(ax, 4.5, yt, 1.3, 0.62, "Step judge\ncode checks, then\nLaya step head", LBLUE, BLUE)
    box(ax, 6.0, yt, 0.9, 0.5, "Tool call\nruns")
    for a, b in [(1.12, 1.36), (2.36, 2.6), (3.6, 3.85), (5.15, 5.55)]:
        arrow(ax, (a, yt), (b, yt))
    ax.text(5.35, yt + 0.12, "ok", fontsize=6.6, color=GREY, style="italic", ha="center")
    arrow(ax, (6.0, yt + 0.25), (3.1, yt + 0.25), "next call", (4.55, 3.07), rad=0.0)
    ax.annotate("", xy=(3.1, yt + 0.25), xytext=(6.0, yt + 0.25))
    box(ax, 4.5, ym, 1.3, 0.5, "Rollback: drop the step,\nresample (up to 2)", LORG, ORG)
    arrow(ax, (4.5, yt - 0.31), (4.5, ym + 0.25), "flag", (4.62, 2.18), ha="left")
    arrow(ax, (3.85, ym + 0.1), (3.3, yt - 0.25), "same doer, new step", (3.35, 1.95), ha="right", color=ORG)
    box(ax, 3.1, yb, 1.3, 0.5, "Doer closes the turn\nwith a message")
    box(ax, 4.9, yb, 1.1, 0.5, "Done check\nLaya done head", LBLUE, BLUE)
    box(ax, 6.2, yb, 0.8, 0.5, "Turn ends")
    arrow(ax, (3.1, yt - 0.25), (3.1, yb + 0.25), "no more calls", (3.0, 1.2), ha="right")
    arrow(ax, (3.75, yb), (4.35, yb))
    arrow(ax, (5.45, yb), (5.8, yb), "done", (5.62, yb + 0.17))
    arrow(ax, (4.9, yb - 0.25), (3.1, yb - 0.25), None, rad=0.0)
    ax.annotate("", xy=(3.1, yb - 0.25), xytext=(4.9, yb - 0.25))
    ax.text(4.0, yb - 0.38, "not done: drop the message, add a note, doer continues (up to 2)", fontsize=6.6, color=ORG, ha="center", style="italic")
    ax.text(0.05, 1.15, "Baseline: the same two judge\nslots filled by a 9B SLM judge\nwith reasoning, about 1,500 to\n2,400 output tokens per step.", fontsize=6.8, color=GREY, va="center", ha="left")
    fig.savefig(os.path.join(OUT, "fig_system.pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_baselines():
    fig, axs = plt.subplots(1, 2, figsize=(6.7, 2.2), gridspec_kw={"width_ratios": [1.25, 1]})
    data = [
        ("BFCL multi turn test, 1,200 runs per system", [("No judge", 15.9, 11.7, 20.5), ("Plain rules", 7.6, 4.4, 11.2), ("SLM judge\n(Qwen3 8B)", 17.4, 12.8, 22.3), ("Laya as is", 0.0, 0.0, 2.2)]),
        ("AgentDojo benign, 291 runs per system", [("No judge", 33.7, 25.4, 42.3), ("Plain rules", 18.2, 12.0, 25.4), ("SLM judge\n(Qwen3 8B)", 25.8, 18.2, 33.7)]),
    ]
    for ax, (title, rows) in zip(axs, data):
        xs = range(len(rows))
        cols = [GREY, ORG, BLUE, "#999999"][: len(rows)]
        ax.bar(xs, [r[1] for r in rows], color=cols, width=0.6)
        ax.errorbar(xs, [r[1] for r in rows], yerr=[[r[1] - r[2] for r in rows], [r[3] - r[1] for r in rows]], fmt="none", ecolor="black", lw=0.9, capsize=3)
        for x, r in zip(xs, rows):
            lab = "0 of 133\n(stopped)" if r[0] == "Laya as is" else f"{r[1]:.1f}"
            ax.text(x, r[3] + 0.9, lab, ha="center", va="bottom", fontsize=6.8)
        ax.set_xticks(list(xs)); ax.set_xticklabels([r[0] for r in rows], fontsize=6.8)
        ax.set_ylim(0, 52 if "Agent" in title else 31); ax.set_ylabel("pass rate, %" if ax is axs[0] else "")
        ax.set_title(title, fontsize=7.4, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_baselines.pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_forest():
    rows = [
        ("Qwen3 8B agent", None),
        ("SLM judge, block and warn", (-7.5, -15.8, -0.8)),
        ("SLM judge + done check", (0.8, -7.5, 9.2)),
        ("Oracle, rollback + done check", (5.8, 0.0, 12.5)),
        ("Qwen3.5 4B agent", None),
        ("SLM judge + done check", (0.8, -5.8, 8.3)),
        ("Oracle, rollback + done check", (9.2, 2.5, 15.8)),
        ("Qwen3.5 9B agent", None),
        ("Laya done check", (2.5, -5.0, 10.8)),
        ("SLM judge (9B) done check", (0.0, -5.8, 7.5)),
        ("Laya step + done, rollback", (-0.8, -7.5, 6.7)),
        ("SLM judge (9B) step + done, rollback", (0.8, -5.0, 7.5)),
        ("Oracle done check", (3.3, -5.0, 12.5)),
        ("Oracle, rollback + done check", (4.2, -1.7, 10.8)),
    ]
    fig, ax = plt.subplots(figsize=(6.7, 3.5))
    n = len(rows)
    for i, (name, v) in enumerate(rows):
        y = n - i
        if v is None:
            ax.text(-33.5, y, name, fontweight="bold", fontsize=7.4, va="center", ha="left")
            continue
        sig = v[1] > 0 or v[2] < 0
        col = (ORG if "Oracle" in name else BLUE) if not sig or True else BLUE
        col = GREY if "Oracle" in name else BLUE
        ax.plot([v[1], v[2]], [y, y], color=col, lw=1.6)
        ax.plot(v[0], y, "o" if not sig else "D", color=col, ms=4.5)
        ax.text(-32.6, y, name, fontsize=7.2, va="center", ha="left")
        ax.text(17.6, y, f"{v[0]:+.1f} [{v[1]:+.1f}, {v[2]:+.1f}]", fontsize=6.8, va="center", ha="left", color=BLUE if sig else "black")
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlim(-33.5, 17.5); ax.set_ylim(-0.4, n + 0.8)
    ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_xticks([-5, 0, 5, 10, 15]); ax.set_xlabel("pass rate change against no judge, points, with 95% CI", fontsize=7)
    ax.text(-33.5, 0.0, "diamond: CI excludes 0. Grey: oracle, a ceiling that cannot be deployed.", fontsize=6.5, color=GREY, ha="left")
    fig.savefig(os.path.join(OUT, "fig_forest.pdf"), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def fig_kappa():
    fig, ax = plt.subplots(figsize=(3.3, 2.3))
    groups = ["Annotator A\nvs checkers", "Annotator B\nvs checkers", "A vs B"]
    v2 = [0.71, 0.66, 0.66]; v3 = [0.84, 0.71, 0.73]
    ax.axhspan(0.6, 0.8, color=LORG, zorder=0)
    ax.axhline(0.7, color=ORG, lw=0.8, ls="--", zorder=1)
    w = 0.34
    for i in range(3):
        ax.bar(i - w / 2, v2[i], w, color="#9AA5B1", zorder=2, label="guide v2 labels" if i == 0 else None)
        ax.bar(i + w / 2, v3[i], w, color=BLUE, zorder=2, label="guide v3 labels" if i == 0 else None)
        ax.text(i - w / 2, v2[i] + 0.01, f"{v2[i]:.2f}", ha="center", fontsize=6.6)
        ax.text(i + w / 2, v3[i] + 0.01, f"{v3[i]:.2f}", ha="center", fontsize=6.6)
    ax.set_xticks(range(3)); ax.set_xticklabels(groups, fontsize=6.6)
    ax.set_ylim(0.4, 1.0); ax.set_ylabel("kappa, 100 fresh steps", fontsize=6.8)
    ax.legend(fontsize=6.3, loc="upper right", frameon=False, ncol=1)
    fig.savefig(os.path.join(OUT, "fig_kappa.pdf"), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def fig_timeline():
    import datetime as dt
    d0 = dt.date(2026, 10, 31)
    def day(m, d): return (dt.date(2026, m, d) - d0).days
    rows = [
        ("Phase 3 reruns scored (done 31 Oct); step head seeds", day(10, 31), day(11, 3) + 1, "run", "Swayam"),
        ("9B test passes, no judge (stop at 300 false claims or 8 passes)", day(11, 1), day(11, 5) + 1, "plan", "Pavan"),
        ("LLM annotation of test steps, guide v3", day(11, 4), day(11, 7) + 1, "plan", "Pavan"),
        ("Human check of 100 test steps, kappa rule", day(11, 6), day(11, 9) + 1, "plan", "Swayam, Aaditya, Pavan"),
        ("Typed closing message head with a false claim class", day(11, 2), day(11, 8) + 1, "plan", "Pavan"),
        ("Ablations: state parts, 3 seeds", day(11, 3), day(11, 10) + 1, "plan", "Shuban, Swayam"),
        ("Test baselines rerun with the 9B agent", day(11, 5), day(11, 10) + 1, "plan", "Pavan, Shuban"),
        ("Primary metric on test, paired bootstrap, Holm", day(11, 9), day(11, 12) + 1, "plan", "Shuban"),
        ("Online test runs with rollback and done check", day(11, 8), day(11, 13) + 1, "plan", "Pavan, Aaditya"),
        ("Escalation budget, 4B pilot, AgentProcessBench, Gemma 4 12B", day(11, 10), day(11, 14) + 1, "opt", "stretch"),
        ("Final report, fact check, label release, repo cleanup", day(11, 11), day(11, 15) + 1, "plan", "all four"),
    ]
    colors = {"run": ORG, "plan": BLUE, "opt": "#B5B5B5"}
    fig, ax = plt.subplots(figsize=(6.7, 3.3))
    n = len(rows)
    for i, (name, s, e, k, who) in enumerate(rows):
        y = n - i
        ax.barh(y, e - s, left=s, height=0.55, color=colors[k], hatch="//" if k == "opt" else None, edgecolor="white" if k != "opt" else "#888888", lw=0.5)
        ax.text(-0.3, y, name, ha="right", va="center", fontsize=6.9)
        ax.text(e + 0.12, y, who, ha="left", va="center", fontsize=6.3, color=GREY)
    ax.axvline(16, color="black", lw=1.0)
    ax.text(15.9, n + 0.85, "final submission\n15 Nov", ha="right", va="bottom", fontsize=6.8, fontweight="bold")
    ax.axvline(0, color=GREY, lw=0.6, ls=":")
    ax.set_xlim(0, 20.2); ax.set_ylim(0.4, n + 1.9)
    ticks = [0, 2, 4, 6, 8, 10, 12, 14]
    ax.set_xticks(ticks); ax.set_xticklabels(["31 Oct", "2 Nov", "4 Nov", "6 Nov", "8 Nov", "10 Nov", "12 Nov", "14 Nov"], fontsize=6.8)
    ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.axvspan(16, 20.2, color=LGREY, zorder=0)
    ax.text(18.1, n + 0.1, "16 to 19 Nov\nevaluations", ha="center", va="center", fontsize=6.6, color=GREY)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ORG, label="in progress"), Patch(color=BLUE, label="planned"), Patch(facecolor="#B5B5B5", hatch="//", edgecolor="#888888", label="stretch, only if time allows")], fontsize=6.5, loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=3, frameon=False)
    fig.savefig(os.path.join(OUT, "fig_timeline.pdf"), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def fig_offline():
    fig, axs = plt.subplots(1, 3, figsize=(6.7, 2.1), gridspec_kw={"width_ratios": [2.2, 1.2, 1.8]})
    ax = axs[0]
    m = ["Precision", "Recall", "F1", "AUROC"]; slm = [0.18, 0.38, 0.24, 0.61]; lay = [0.57, 0.61, 0.59, 0.91]
    import numpy as np
    x = np.arange(4); w = 0.36
    ax.bar(x - w / 2, slm, w, color="#9AA5B1", label="9B SLM judge"); ax.bar(x + w / 2, lay, w, color=BLUE, label="Laya finetuned")
    for i in range(4):
        ax.text(i - w / 2, slm[i] + 0.015, f"{slm[i]:.2f}", ha="center", fontsize=6.3); ax.text(i + w / 2, lay[i] + 0.015, f"{lay[i]:.2f}", ha="center", fontsize=6.3)
    ax.set_xticks(x); ax.set_xticklabels(m, fontsize=6.8); ax.set_ylim(0, 1.12); ax.legend(fontsize=6.3, frameon=False, loc="upper left")
    ax.set_title("(a) Step check, 1,277 val calls", fontsize=7.2, loc="left")
    ax = axs[1]
    names = ["as is", "head only", "full"]; au = [0.53, 0.59, 0.79]
    ax.bar(range(3), au, color=[LBLUE, "#8FB1D3", BLUE], width=0.6)
    for i, v in enumerate(au): ax.text(i, v + 0.015, f"{v:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(range(3)); ax.set_xticklabels(names, fontsize=6.6); ax.set_ylim(0, 1.0)
    ax.set_title("(b) Done check AUROC", fontsize=7.2, loc="left")
    ax = axs[2]
    names = ["Laya full\nthr 0.5", "Laya full\nCV thr 0.56", "Laya full\ndev thr", "9B SLM\njudge"]; f1 = [0.53, 0.53, 0.36, 0.41]
    ax.bar(range(4), f1, color=[BLUE, BLUE, ORG, "#9AA5B1"], width=0.6)
    for i, v in enumerate(f1): ax.text(i, v + 0.015, f"{v:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(range(4)); ax.set_xticklabels(names, fontsize=5.8); ax.set_ylim(0, 0.7)
    ax.set_title("(c) Done check F1", fontsize=7.2, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_offline.pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    fig_forest(); fig_kappa(); fig_timeline(); fig_offline()
