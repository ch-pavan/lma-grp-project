# Figures for the final report that are new since the mid submission. Numbers are typed in, each with its source file
# (paths in the repo after merging pavan/test-results into main). Figures reused from the mid report are copied from
# mid_submission/condensed/figs/. Same colours as the mid report: blue = Laya, grey = 9B SLM judge, orange = the typed
# closing-message head, dark grey = oracle.
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
BLUE, ORG, JUDGE, DARK, LBLUE = "#2F5D8A", "#C8651B", "#9AA5B1", "#555555", "#DCE8F4"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#888888", "xtick.color": "#333333", "ytick.color": "#333333"})


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def fig_live_test():
    """(a) Pass rate change against no judge on the 1,200 test tasks, rollback plus done check.
    Source: analysis/rb_test_results.py (Ada) and analysis/live_compare.py (typed head, cloud).
    (b) Pass rate against seconds per task, Ada runs: task logs in runs/raw/q9b_test/."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.35), gridspec_kw={"width_ratios": [1.25, 1]})
    rows = [("Laya (frozen)", 3.7, 0.8, 6.8, BLUE),
            ("Laya, typed closing head", 3.2, 0.4, 6.2, ORG),
            ("9B SLM judge", 3.7, 1.1, 6.5, JUDGE),
            ("Oracle (ceiling)", 10.3, 7.0, 13.8, DARK)]
    for i, (name, m, lo, hi, c) in enumerate(rows):
        y = len(rows) - i
        a.plot([lo, hi], [y, y], color=c, lw=2, solid_capstyle="round")
        a.plot(m, y, "D", color=c, ms=5.5, mec="white", mew=0.8)
        a.text(hi + 0.5, y, f"{m:+.1f} [{lo:+.1f}, {hi:+.1f}]", va="center", fontsize=6.8, color="#222222")
    a.axvline(0, color="#333333", lw=0.8)
    a.set_yticks(range(len(rows), 0, -1)); a.set_yticklabels([r[0] for r in rows], fontsize=7)
    a.set_xlim(-1.5, 20.5); a.set_ylim(0.4, len(rows) + 0.6)
    a.set_xlabel("pass rate change against no judge, points (95% CI)", fontsize=6.8)
    a.grid(axis="x", color="#E5E5E5", lw=0.6); a.set_axisbelow(True)
    a.set_title("(a) Gain over no judge, 1,200 test tasks each", fontsize=7.5, loc="left")

    pts = [("No judge", 426, 45.5, "#BBBBBB"), ("Laya", 528, 49.2, BLUE), ("9B SLM judge", 1621, 49.2, JUDGE),
           ("Oracle", 691, 55.8, DARK)]
    for name, s, p, c in pts:
        b.scatter(s, p, s=46, color=c, edgecolor="white", linewidth=1.0, zorder=3)
    b.annotate("No judge 45.5%", (426, 45.5), (300, 43.5), fontsize=6.7)
    b.annotate("Laya 49.2%, 0 judge tokens", (528, 49.2), (560, 46.1), fontsize=6.7, color=BLUE, fontweight="bold")
    b.annotate("9B SLM judge 49.2%\n52.7k judge tokens per task", (1621, 49.2), (1180, 51.2), fontsize=6.7)
    b.annotate("Oracle 55.8%", (691, 55.8), (760, 55.3), fontsize=6.7)
    b.annotate("", (1580, 48.9), (575, 48.9), arrowprops=dict(arrowstyle="<->", color="#777777", lw=0.8))
    b.text(1100, 48.0, "9B judge: 3.1x the time per task", fontsize=6.5, color="#555555", ha="center")
    b.set_xlim(250, 1850); b.set_ylim(43, 58)
    b.set_xlabel("seconds per task (Ada, 2 x RTX 2080 Ti)", fontsize=6.8); b.set_ylabel("test pass rate, %", fontsize=6.8)
    b.grid(color="#E5E5E5", lw=0.6); b.set_axisbelow(True)
    b.set_title("(b) Same accuracy, a third of the time", fontsize=7.5, loc="left")
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig_live_test.pdf")


def fig_primary_test():
    """Primary metric on the 7,214 labelled test steps. Source: runs/raw/typed_head/primary_test.md."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.4), gridspec_kw={"width_ratios": [1.15, 1]})
    sets = ["DeepSeek v3", "GLM v3", "Both agree"]
    sysv = [("9B SLM judge", [0.246, 0.245, 0.240], JUDGE), ("Laya frozen", [0.076, 0.078, 0.063], BLUE),
            ("Laya typed", [0.436, 0.376, 0.405], ORG)]
    w = 0.26
    for j, (name, vals, c) in enumerate(sysv):
        xs = [i + (j - 1) * (w + 0.02) for i in range(3)]
        a.bar(xs, vals, w, color=c, label=name, zorder=2)
        for x, v in zip(xs, vals):
            a.text(x, v + 0.008, f"{v:.2f}", ha="center", fontsize=6.4)
    for i, d in enumerate(["+19.0", "+13.1", "+16.5"]):
        a.text(i + w + 0.02, [0.436, 0.376, 0.405][i] + 0.04, d, ha="center", fontsize=6.6, color=ORG, fontweight="bold")
    a.set_xticks(range(3)); a.set_xticklabels(sets, fontsize=7)
    a.set_ylim(0, 0.53); a.set_ylabel("primary F1 (mean of off track and false claim)", fontsize=6.5)
    a.grid(axis="y", color="#E5E5E5", lw=0.6); a.set_axisbelow(True)
    a.legend(fontsize=6.4, frameon=False, loc="upper right", ncol=3, bbox_to_anchor=(1.0, 1.13))
    a.set_title("(a) Primary metric by label set", fontsize=7.5, loc="left", pad=14)

    kinds = ["Off track,\ntool calls", "Off track,\nclosing messages", "False claim"]
    vals = [("9B SLM judge", [0.17, 0.29, 0.25], JUDGE), ("Laya frozen", [0.23, 0.00, 0.04], BLUE),
            ("Laya typed", [0.23, 0.72, 0.19], ORG)]
    for j, (name, v, c) in enumerate(vals):
        xs = [i + (j - 1) * (w + 0.02) for i in range(3)]
        b.bar(xs, v, w, color=c, zorder=2)
        for x, y in zip(xs, v):
            b.text(x, y + 0.012, f"{y:.2f}", ha="center", fontsize=6.4)
    b.set_xticks(range(3)); b.set_xticklabels(kinds, fontsize=6.8)
    b.set_ylim(0, 0.82); b.set_ylabel("F1, labels where both annotators agree", fontsize=6.5)
    b.grid(axis="y", color="#E5E5E5", lw=0.6); b.set_axisbelow(True)
    b.set_title("(b) Where the gain comes from", fontsize=7.5, loc="left", pad=14)
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig_primary_test.pdf")


def fig_failures():
    """Why the 9B agent fails on test: type of the first failed turn of each failed task, 1,711 of 3,200 tasks.
    Source: runs/raw/test9b/oracle_labels.log (analysis/oracle_labels.py)."""
    rows = [("Stopped early", 24.8, "omission"), ("Asked the user instead of acting", 24.3, "omission"),
            ("Acted when it should have asked", 16.8, "step"), ("Took a wrong step", 15.3, "step"),
            ("Said \"done\" when it was not", 14.7, "omission"), ("Checker only / step cap", 4.0, "other")]
    col = {"omission": ORG, "step": BLUE, "other": "#BBBBBB"}
    fig, ax = plt.subplots(figsize=(4.2, 1.95))
    for i, (name, v, k) in enumerate(rows):
        y = len(rows) - i
        ax.barh(y, v, 0.62, color=col[k], zorder=2)
        ax.text(v + 0.5, y, f"{v:.1f}%", va="center", fontsize=6.8)
    ax.set_yticks(range(len(rows), 0, -1)); ax.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax.set_xlim(0, 30); ax.set_xlabel("share of failed test tasks, %", fontsize=6.8)
    ax.grid(axis="x", color="#E5E5E5", lw=0.6); ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ORG, label="unfinished turn: only a turn-end check sees it"),
                       Patch(color=BLUE, label="bad step: a step check sees it")],
              fontsize=6.2, frameon=False, loc="upper center", bbox_to_anchor=(0.4, -0.28), ncol=2)
    save(fig, "fig_failures.pdf")


def fig_typed_val():
    """Typed head on validation, 3 seeds, primary minus the 9B judge. Source: runs/raw/typed_head/select.log and
    analysis/2026-11-09_typed_closing_head.md."""
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    sets = ["DeepSeek v2", "GLM v2", "Both agree"]
    frozen = [0.5, 2.2, 3.8]
    seeds = [[14.8, 10.2, 11.5], [12.5, 10.1, 9.3], [13.9, 10.6, 11.2]]
    w = 0.19
    ax.bar([i - 1.5 * w for i in range(3)], frozen, w, color=BLUE, label="Laya frozen", zorder=2)
    for s in range(3):
        ax.bar([i + (s - 0.5) * w for i in range(3)], seeds[s], w, color=ORG, alpha=[1, 0.75, 0.55][s],
               label="typed head, seeds 0, 1, 2" if s == 0 else None, zorder=2)
    ax.axhline(9, color="#333333", lw=0.8, ls="--", label="proposal bar, +9 points")
    ax.set_xticks(range(3)); ax.set_xticklabels(sets, fontsize=7)
    ax.set_ylabel("primary, Laya minus 9B judge, points", fontsize=6.5)
    ax.set_ylim(0, 17); ax.grid(axis="y", color="#E5E5E5", lw=0.6); ax.set_axisbelow(True)
    ax.legend(fontsize=6.2, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.45, 1.0))
    save(fig, "fig_typed_val.pdf")


def fig_versions():
    """Live pass rate by BFCL version on test, Ada runs (task logs in runs/raw/q9b_test/)."""
    vers = ["base", "missing\nparameter", "missing\nfunction", "long\ncontext"]
    data = [("No judge", [58.3, 39.3, 29.3, 55.0], "#BBBBBB"), ("Laya", [63.3, 39.7, 32.7, 61.0], BLUE),
            ("9B SLM judge", [61.3, 41.7, 34.0, 59.7], JUDGE), ("Oracle", [69.0, 50.3, 38.3, 65.7], DARK)]
    fig, ax = plt.subplots(figsize=(4.3, 2.05))
    w = 0.2
    for j, (name, v, c) in enumerate(data):
        xs = [i + (j - 1.5) * (w + 0.015) for i in range(4)]
        ax.bar(xs, v, w, color=c, label=name, zorder=2)
    ax.set_xticks(range(4)); ax.set_xticklabels(vers, fontsize=6.8)
    ax.set_ylabel("pass rate, %", fontsize=6.8); ax.set_ylim(0, 78)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6); ax.set_axisbelow(True)
    ax.legend(fontsize=6.2, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.13))
    save(fig, "fig_versions.pdf")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_live_test(); fig_primary_test(); fig_failures(); fig_typed_val()
    print("figures written to", OUT)
