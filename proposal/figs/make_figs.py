#!/usr/bin/env python3
"""Draw the proposal figures: d1 (baseline vs ours), d2 (judge questions and actions),
d3 (training and test labels), d4 (systems compared), d5 (timeline)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent
BLUE = "#1a6fe8"
FILL = "#edf1fb"
GREY = "#555555"
ORANGE = "#d9780b"
ORANGE_FILL = "#fff4e6"
plt.rcParams["font.family"] = "DejaVu Sans"


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, hl=False, warn=False, size=10, bold=False):
    ec, fc, lw = (BLUE, FILL, 2.4) if hl else (GREY, "white", 1.6)
    if warn:
        ec, fc = ORANGE, ORANGE_FILL
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                ec=ec, fc=fc, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
            fontweight="bold" if bold else "normal", linespacing=1.3)


def arrow(ax, x1, y1, x2, y2, color=GREY, style="-|>", ls="-", rad=0.0, lw=1.5):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13,
                                 color=color, lw=lw, ls=ls, connectionstyle=f"arc3,rad={rad}"))


def title(ax, x, y, text, color="#333333", size=11):
    ax.text(x, y, text, fontsize=size, fontweight="bold", color=color, va="center")


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def d1():
    fig, ax = canvas(11, 5.2)
    rows = [
        (3.9, "Baseline: generator and LLM judge", "#333333", GREY, False,
         "Judge\nLLM, Qwen3.5 9B,\nreasoning on"),
        (1.2, "Ours: same agents, the judge is a small classifier", BLUE, BLUE, True,
         "Judge\nLaya 0.4B, unsure\nsteps go to the LLM"),
    ]
    for y, head, col, ac, hl, judge in rows:
        title(ax, 0.15, y + 1.25, head, col, 11.5)
        xs = [0.15, 1.95, 4.35, 6.75, 9.3]
        ws = [1.4, 1.9, 1.9, 2.2, 1.55]
        labels = ["Task", "Planner\nQwen3.5 9B", "Doer agents,\none per\nplan step", judge,
                  "Next step\nor answer"]
        for i, (x, w, t) in enumerate(zip(xs, ws, labels)):
            box(ax, x, y, w, 0.95, t, hl=(hl and i == 3), size=9.5)
            if i < 4:
                arrow(ax, x + w, y + 0.47, xs[i + 1], y + 0.47)
        arrow(ax, 7.8, y - 0.05, 5.3, y - 0.05, color=ac, ls="--", rad=-0.35)
        ax.text(6.55, y - 0.72, "same questions, same fixed rules", ha="center", fontsize=9, color=ac)
    save(fig, "d1.png")


def d2():
    fig, ax = canvas(12, 6.2)
    title(ax, 0.1, 5.95, "1. State and code checks")
    title(ax, 4.0, 5.95, "2. Typed questions", BLUE)
    title(ax, 8.1, 5.95, "3. Fixed rules pick the action")
    box(ax, 0.1, 2.0, 3.2, 3.5,
        "State, 1,024 tokens\n\nrequests, turn plan,\nproposed call or\nclosing message,\nevidence list,\nlast three calls", size=9.5)
    box(ax, 0.1, 0.35, 3.2, 1.3, "Code checks first:\nexact repeat, irreversible\ntool list, evidence list", size=9)
    qs = [("Q1 Drift", "on_track | off_track", 4.35),
          ("Q2 Hallucination", "none | made_up_value | false_claim", 3.05),
          ("Q3 Needed (irreversible calls)", "needed | not_needed", 1.75)]
    for name, opts, y in qs:
        box(ax, 3.9, y, 3.7, 1.0, "", hl=True)
        ax.text(5.75, y + 0.68, name, ha="center", fontsize=10, fontweight="bold", color=BLUE)
        ax.text(5.75, y + 0.3, opts, ha="center", fontsize=8.8)
        arrow(ax, 3.3, 3.75, 3.9, y + 0.5, color="#9aa7c0")
    ax.text(5.75, 1.1, "one forward pass each, every answer\na fixed option with a confidence", ha="center", fontsize=8.8,
            color="#444444")
    box(ax, 4.2, 0.15, 3.1, 0.55, "low confidence: ask LLM judge", warn=True, size=8.8)
    acts = [("All fine", "the call runs", 5.1, False),
            ("Q3 not_needed", "ask the user", 4.25, True),
            ("Off track or hallucination", "block, fixed warning to doer", 3.4, False),
            ("Second flag in the turn", "fresh doer from last good step", 2.55, False),
            ("Exact repeat", "backtrack before the loop", 1.7, False)]
    for t, d, y, warn in acts:
        box(ax, 8.1, y, 3.8, 0.7, "", hl=not warn and t != "All fine", warn=warn)
        ax.text(10.0, y + 0.47, t, ha="center", fontsize=9.3, fontweight="bold")
        ax.text(10.0, y + 0.2, d, ha="center", fontsize=8.6, color="#333333")
    arrow(ax, 7.6, 4.85, 8.1, 3.8, color="#9aa7c0")
    arrow(ax, 7.6, 3.55, 8.1, 3.7, color="#9aa7c0")
    arrow(ax, 7.6, 2.25, 8.1, 4.55, color="#9aa7c0")
    ax.text(10.0, 1.15, "Rollback restores reversible calls only", ha="center", fontsize=8.8, color="#444444")
    save(fig, "d2.png")


def d3():
    fig, ax = canvas(12, 6.6)
    title(ax, 0.1, 6.35, "Training labels (automatic, confirmed by replay and code checks)")
    box(ax, 0.1, 4.75, 2.9, 1.1, "Natural runs\nQwen3.5 9B x3, 4B x1\ntraining scenarios", size=9)
    box(ax, 0.1, 3.45, 2.9, 1.1, "Directed runs\nQwen3.8 27B told to make\none named error", size=9)
    box(ax, 3.7, 3.95, 3.0, 1.5, "Step labels for Q1 to Q3\nBFCL replay, evidence list,\nreference solutions", size=9.2)
    box(ax, 7.4, 3.95, 2.0, 1.5, "Checked by the\ntwo annotators,\nrules fixed at\n80% agreement", size=8.8)
    box(ax, 10.0, 3.95, 1.9, 1.5, "Finetune\nLaya 0.4B", hl=True, size=9.5)
    arrow(ax, 3.0, 5.3, 3.7, 4.9)
    arrow(ax, 3.0, 4.0, 3.7, 4.5)
    arrow(ax, 6.7, 4.7, 7.4, 4.7)
    arrow(ax, 9.4, 4.7, 10.0, 4.7)

    title(ax, 0.1, 2.85, "Test labels (natural Qwen3.5 9B errors only)")
    box(ax, 0.1, 1.15, 2.6, 1.3, "3 recorded test passes\nfailed turns to the first\noff track call, plus\npassed turns", size=8.6)
    box(ax, 3.3, 1.7, 2.9, 0.85, "Annotator A\nDeepSeek V4.1 Flash", hl=True, size=9)
    box(ax, 3.3, 0.6, 2.9, 0.85, "Annotator B\nGLM-5.3", hl=True, size=9)
    box(ax, 6.8, 1.15, 2.2, 1.3, "Cohen's kappa\nand Gwet's AC1\nbetween A and B", size=9)
    box(ax, 9.6, 1.7, 2.3, 0.85, "Disagreements:\none of us decides", size=8.8)
    box(ax, 9.6, 0.6, 2.3, 0.85, "Check: 200 steps,\ntwo of us + third,\nkappa at least 0.7", warn=True, size=8.2)
    arrow(ax, 2.7, 1.9, 3.3, 2.1)
    arrow(ax, 2.7, 1.5, 3.3, 1.05)
    arrow(ax, 6.2, 2.1, 6.8, 1.9)
    arrow(ax, 6.2, 1.05, 6.8, 1.6)
    arrow(ax, 9.0, 1.95, 9.6, 2.1)
    arrow(ax, 9.0, 1.5, 9.6, 1.1, ls="--")
    save(fig, "d3.png")


def d4():
    fig, ax = canvas(12, 4.6)
    box(ax, 0.1, 1.7, 2.1, 1.3, "BFCL multi turn\n200 scenarios,\n4 versions each", size=9.2)
    box(ax, 2.9, 3.1, 2.0, 0.85, "training, whatever is\nleft after cleaning", size=8.6)
    box(ax, 2.9, 1.85, 2.0, 0.85, "15 validation", size=9)
    box(ax, 2.9, 0.45, 2.0, 1.15, "100 test scenarios\n3 runs each", hl=True, size=9)
    arrow(ax, 2.2, 2.6, 2.9, 3.5)
    arrow(ax, 2.2, 2.35, 2.9, 2.3)
    arrow(ax, 2.2, 2.0, 2.9, 1.2)
    ax.add_patch(FancyBboxPatch((5.5, 0.2), 4.2, 4.2, boxstyle="round,pad=0,rounding_size=0.1",
                                ec="#bbbbbb", fc="none", lw=1.4, ls="--"))
    ax.text(7.6, 4.18, "7 online systems, same tasks and runs", ha="center", fontsize=10, fontweight="bold")
    sy = [("No judge", False), ("Plain rules", False), ("LLM judge, reasoning on", False),
          ("Laya as is", True), ("Granite Guardian 3B", False), ("Laya finetuned", True),
          ("Full system: finetuned\n+ escalation", True)]
    for i, (t, hl) in enumerate(sy):
        col, row = i % 2, i // 2
        w = 1.95
        box(ax, 5.65 + col * 2.05, 3.05 - row * 0.9, w, 0.75, t, hl=hl, size=8.2)
    arrow(ax, 4.9, 1.0, 5.5, 1.9)
    box(ax, 10.2, 1.4, 1.75, 1.9, "Task accuracy\nTool call accuracy\nUnneeded irreversible\ncalls run\nTokens and time", size=8.2)
    arrow(ax, 9.7, 2.35, 10.2, 2.35)
    save(fig, "d4.png")


def d5():
    fig, ax = plt.subplots(figsize=(12.4, 4.6))
    phases = [
        ("Phase 1: set up, clean BFCL, pilot, natural and directed runs, label checks", 1, 10.5),
        ("Phase 2: finetune, annotator labels on test steps, offline scores, ablations", 10.5, 21),
        ("Phase 3: online runs (baselines first), failure analysis, write up", 21, 30.5),
    ]
    for i, (name, a, b) in enumerate(phases):
        y = 3 - i
        ax.barh(y, b - a, left=a, height=0.38, color=FILL, edgecolor=BLUE, lw=2)
        ax.text(1, y + 0.42, name, fontsize=11, va="center")
    for g, x in (("Gate 1", 10.5), ("Gate 2", 21)):
        ax.axvline(x, color="#444444", ls="--", lw=1.4, ymax=0.95)
        ax.text(x, 3.95, g, ha="center", fontsize=12, fontweight="bold")
    ax.set_xlim(0.5, 31)
    ax.set_ylim(0.3, 4.1)
    ax.set_yticks([])
    ax.set_xticks([1, 8, 15, 22, 29])
    ax.set_xticklabels([f"day {d}" for d in (1, 8, 15, 22, 29)], fontsize=11)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    save(fig, "d5.png")


if __name__ == "__main__":
    d1(); d2(); d3(); d4(); d5()
    print("wrote d1 to d5")
