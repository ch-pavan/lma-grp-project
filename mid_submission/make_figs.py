#!/usr/bin/env python3
"""Figures for the mid-submission report (LaTeX). Writes vector PDFs to mid_submission/figs/.

Colour palette: Okabe-Ito (colour-blind safe). Every number is copied from a result file in the repo; the source is
named in each function's docstring, so the figures and the report's tables agree.

    python mid_submission/make_figs.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent / "figs"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Arial"], "font.size": 8.5,
    "axes.edgecolor": "#333333", "axes.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#e3e3e3", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "pdf.fonttype": 42,
})
BLUE, ORANGE, SKY, GREEN, VERM, GREY = "#0072B2", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#8c8c8c"
LIGHTBLUE, LIGHTGREY, LIGHTGREEN, LIGHTVERM = "#d4e6f5", "#ececec", "#d5efe6", "#f8ddd0"


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def system_diagram():
    """Figure 1: where the two Laya checks sit in the planner and doer loop."""
    fig, ax = plt.subplots(figsize=(7.4, 2.75))
    ax.set_xlim(0, 102); ax.set_ylim(0, 38); ax.axis("off"); ax.grid(False)

    def box(x, y, w, h, text, fc="white", ec="#333333", bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.0", fc=fc, ec=ec, lw=0.9))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.3,
                fontweight="bold" if bold else "normal", linespacing=1.25)

    def arrow(x1, y1, x2, y2, text=None, dx=0, dy=0):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=0.9, color="#333333", shrinkA=0, shrinkB=0, mutation_scale=8))
        if text:
            ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, text, ha="center", va="center", fontsize=6.6, style="italic")

    ax.text(0, 36.5, "Each step", fontsize=7.5, fontweight="bold", va="center")
    ax.text(0, 15.5, "End of each turn", fontsize=7.5, fontweight="bold", va="center")
    y, h = 23, 9
    box(0, y, 10, h, "User\nrequest")
    box(13, y, 12, h, "Planner\nwrites a plan")
    box(28, y, 12, h, "Doer\nproposes a\ntool call")
    box(43, y, 13, h, "Code: repeat\ncheck, builds\nevidence list", fc=LIGHTGREY)
    box(59, y, 15, h, "Laya step head\n0.4B classifier\none pass", fc=LIGHTBLUE, ec=BLUE, bold=True)
    box(79, 28.5, 21, 6, "ok: run the tool call", fc=LIGHTGREEN, ec=GREEN)
    box(79, 20.5, 21, 6, "bad: roll back, doer\nresamples the step", fc=LIGHTVERM, ec=VERM)
    for x1, x2 in ((10, 13), (25, 28), (40, 43), (56, 59)):
        arrow(x1, y + h / 2, x2, y + h / 2)
    arrow(74, 29, 79, 31.5); arrow(74, 25.5, 79, 23.5)

    y2 = 2
    box(26, y2, 15, h, "Doer ends\nthe turn with a\nclosing message")
    box(44, y2, 15, h, "Laya done head\n0.4B classifier\none pass", fc=LIGHTBLUE, ec=BLUE, bold=True)
    box(63, 7.5, 22, 6, "done: turn ends", fc=LIGHTGREEN, ec=GREEN)
    box(63, 0, 22, 6, "not done: drop message,\nagent continues", fc=LIGHTVERM, ec=VERM)
    arrow(34, y, 34, y2 + h, "after the\nlast step", dx=-5)
    arrow(41, y2 + h / 2, 44, y2 + h / 2)
    arrow(59, 8, 63, 10.5); arrow(59, 5, 63, 3)
    ax.text(95.5, 7, "Baseline: the 9B SLM\njudge takes both blue\nplaces and writes about\n1,500 to 2,400 tokens\nper check",
            ha="center", va="center", fontsize=6.5, style="italic", color="#a35f00")
    save(fig, "fig1_system")


def agents():
    """Figure 2. Source: analysis/2026-10-24_qwen35_9b_baseline.md, 'Pass rates'."""
    rows = [("Qwen3 8B", 25.8, 9.2, 44.2), ("Qwen3.5 4B", 40.0, 24.2, 55.8),
            ("Qwen3.5 9B, reasoning on", 36.7, 20.0, 53.3), ("Qwen3.5 9B, reasoning off (ours)", 43.3, 27.5, 60.0)]
    fig, ax = plt.subplots(figsize=(4.4, 1.8))
    ax.grid(axis="x", color="#e3e3e3"); ax.grid(axis="y", visible=False)
    for i, (n, p, lo, hi) in enumerate(rows):
        ax.barh(i, p, color=BLUE if i == 3 else SKY, height=0.62)
        ax.errorbar(p, i, xerr=[[p - lo], [hi - p]], fmt="none", ecolor="#222222", elinewidth=0.8, capsize=2.5)
        ax.text(hi + 1.2, i, f"{p:.1f}", va="center", fontsize=7.5)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows]); ax.set_xlim(0, 70)
    ax.set_xlabel("BFCL pass % on 120 validation tasks (95% CI)")
    save(fig, "fig2_agents")


def test_baselines():
    """Figure 3. Source: shuban_findings/results/test_baselines.md."""
    names = ["S1 no judge", "S2 plain rules", "S3 SLM judge"]
    bfcl = [(15.9, 11.7, 20.5), (7.6, 4.4, 11.2), (17.4, 12.8, 22.3)]
    ad = [(33.7, 25.4, 42.3), (18.2, 12.0, 25.4), (25.8, 18.2, 33.7)]
    fig, ax = plt.subplots(figsize=(4.6, 2.0))
    w = 0.36
    for k, (data, lab, col) in enumerate([(bfcl, "BFCL test (1,200 runs)", BLUE), (ad, "AgentDojo (291 runs)", ORANGE)]):
        xs = [i + (k - 0.5) * w for i in range(3)]
        ax.bar(xs, [d[0] for d in data], w, color=col, label=lab)
        ax.errorbar(xs, [d[0] for d in data], yerr=[[d[0] - d[1] for d in data], [d[2] - d[0] for d in data]],
                    fmt="none", ecolor="#222222", elinewidth=0.8, capsize=2.5)
    ax.set_xticks(range(3), names); ax.set_ylabel("Pass % (95% CI)"); ax.set_ylim(0, 50)
    ax.legend(loc="upper right", fontsize=7, ncol=2, bbox_to_anchor=(1.0, 1.13))
    save(fig, "fig3_test_baselines")


def offline_laya():
    """Figure 4. Source: analysis/2026-10-24_qwen35_9b_baseline.md, 'Offline per step' table and 'Laya finetune on
    the turn end done check' table."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.1), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    metrics = ["Precision", "Recall", "F1", "AUROC"]
    j9 = [0.18, 0.38, 0.24, 0.61]; laya = [0.57, 0.61, 0.59, 0.91]
    w = 0.36
    ax.bar([i - w / 2 for i in range(4)], j9, w, color=ORANGE, label="9B SLM judge")
    ax.bar([i + w / 2 for i in range(4)], laya, w, color=BLUE, label="Laya, finetuned")
    for i in range(4):
        ax.text(i - w / 2, j9[i] + 0.02, f"{j9[i]:.2f}", ha="center", fontsize=6.5)
        ax.text(i + w / 2, laya[i] + 0.02, f"{laya[i]:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(range(4), metrics); ax.set_ylim(0, 1.05)
    ax.set_title("(a) Step check, 1,277 validation calls", fontsize=8)
    ax.legend(fontsize=7, loc="upper left")
    ax = axes[1]
    names = ["Laya\nas is", "Laya\nhead only", "Laya\nfull", "9B SLM\njudge"]
    f1 = [0.20, 0.35, 0.53, 0.41]
    cols = ["#b9d7ee", SKY, BLUE, ORANGE]
    for i in range(4):
        ax.bar(i, f1[i], 0.62, color=cols[i])
        ax.text(i, f1[i] + 0.02, f"{f1[i]:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(range(4), names); ax.set_ylim(0, 0.7); ax.set_ylabel("F1 (not done)")
    ax.set_title("(b) Done check, 495 validation turn ends", fontsize=8)
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig4_offline_laya")


def live():
    """Figure 5. Source: analysis/2026-10-24_qwen35_9b_baseline.md, 'Live done check' (job 49274) and
    'Live step check on val' (rbh2dc)."""
    rows = [("Done check: Laya", 2.5, -5.0, 10.8, BLUE, "s"), ("Done check: 9B SLM judge", 0.0, -5.8, 7.5, ORANGE, "s"),
            ("Done check: oracle (ceiling)", 3.3, -5.0, 12.5, GREY, "D"),
            ("Step + done: Laya", -0.8, -7.5, 6.7, BLUE, "s"), ("Step + done: 9B SLM judge", 0.8, -5.0, 7.5, ORANGE, "s"),
            ("Step + done: oracle (ceiling)", 4.2, -1.7, 10.8, GREY, "D"), ("No judge, rerun", 0.0, -6.7, 6.7, "#222222", "o")]
    fig, ax = plt.subplots(figsize=(4.9, 2.25))
    ax.grid(axis="x", color="#e3e3e3"); ax.grid(axis="y", visible=False)
    for i, (n, d, lo, hi, col, mk) in enumerate(rows[::-1]):
        ax.errorbar(d, i, xerr=[[d - lo], [hi - d]], fmt=mk, color=col, ms=4.5, elinewidth=1.1, capsize=2.5)
    ax.axvline(0, color="#333333", lw=0.7, ls="--")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
    ax.set_xlabel("Pass rate minus no judge, points (95% paired CI, 120 tasks)")
    save(fig, "fig5_live")


def agreement():
    """Figure 6. Source: human_check/pilot/results.md, results_v3.md; human_check/val2/results.md, results_v3.md
    (headline row, reweighted kappa); pooled 200-step values in analysis/2026-10-30_guide_v3.md."""
    groups = ["Pilot\nguide v2", "Fresh sample\nguide v2", "Fresh sample\nguide v3", "All 200 steps\nguide v3"]
    a = [0.42, 0.71, 0.84, 0.87]; b = [0.60, 0.66, 0.71, 0.71]
    fig, ax = plt.subplots(figsize=(5.0, 2.1))
    w = 0.36
    ax.bar([i - w / 2 for i in range(4)], a, w, color=BLUE, label="Annotator A (DeepSeek)")
    ax.bar([i + w / 2 for i in range(4)], b, w, color=ORANGE, label="Annotator B (GLM)")
    for i in range(4):
        ax.text(i - w / 2, a[i] / 2, f"{a[i]:.2f}", ha="center", va="center", fontsize=7, color="white", fontweight="bold")
        ax.text(i + w / 2, b[i] / 2, f"{b[i]:.2f}", ha="center", va="center", fontsize=7, color="white", fontweight="bold")
    ax.axhline(0.7, color=GREEN, lw=1.0, ls="--"); ax.text(3.75, 0.7, " pass bar 0.7", fontsize=6.5, va="center", color=GREEN)
    ax.axhline(0.6, color=VERM, lw=0.9, ls=":"); ax.text(3.75, 0.6, " rewrite below 0.6", fontsize=6.5, va="center", color=VERM)
    ax.axhline(0.8, color=GREY, lw=0.8, ls=":"); ax.text(3.75, 0.8, " stop at 200 above 0.8", fontsize=6.5, va="center", color=GREY)
    ax.set_xticks(range(4), groups); ax.set_ylim(0, 1.05); ax.set_xlim(-0.55, 3.75)
    ax.set_ylabel("Kappa vs human check")
    ax.legend(fontsize=7, loc="upper left", ncol=2, bbox_to_anchor=(0, 1.1))
    save(fig, "fig6_agreement")


def timeline():
    """Figure 7: plan to the final submission on 15 November 2026 (same plan as the condensed report)."""
    import datetime as dt
    from matplotlib.patches import Patch
    d0 = dt.date(2026, 10, 31)
    day = lambda m, d: (dt.date(2026, m, d) - d0).days
    tasks = [("Step-head seeds (Ada reruns done)", day(10, 31), day(11, 3) + 1, False),
             ("9B test passes (4, up to 8)", day(11, 1), day(11, 7) + 1, True),
             ("LLM annotation of test steps (v3)", day(11, 3), day(11, 7) + 1, True),
             ("Human check of 100 test steps", day(11, 5), day(11, 9) + 1, True),
             ("False-claim head, frozen before test", day(11, 2), day(11, 9) + 1, False),
             ("State-part ablation, 3 seeds; baselines on 9B", day(11, 3), day(11, 10) + 1, False),
             ("Primary metric on test", day(11, 9), day(11, 13) + 1, True),
             ("Online test runs", day(11, 9), day(11, 13) + 1, False),
             ("Final report, label release", day(11, 11), day(11, 15) + 1, True)]
    fig, ax = plt.subplots(figsize=(6.6, 2.3))
    ax.grid(axis="y", visible=False)
    for i, (n, s_, e_, crit) in enumerate(tasks[::-1]):
        ax.barh(i, e_ - s_, left=s_, height=0.55, color=VERM if crit else SKY)
    ax.set_yticks(range(len(tasks)), [x[0] for x in tasks[::-1]])
    ticks = [day(10, 31), day(11, 3), day(11, 7), day(11, 11), day(11, 15)]
    ax.set_xticks(ticks, ["31 Oct", "3 Nov", "7 Nov", "11 Nov", "15 Nov"])
    ax.axvline(day(11, 15) + 1, color="#333333", lw=0.9, ls="--")
    ax.text(day(11, 15) + 1.2, len(tasks) - 0.6, "final\n15 Nov", fontsize=6.5, va="top")
    ax.set_xlim(0, day(11, 15) + 3.5)
    ax.legend(handles=[Patch(color=VERM, label="critical path"), Patch(color=SKY, label="other work")],
              fontsize=6.8, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.16))
    save(fig, "fig7_timeline")


if __name__ == "__main__":
    for f in (system_diagram, agents, test_baselines, offline_laya, live, agreement, timeline):
        f()
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
