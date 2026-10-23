"""Figures: tracker funnel, labels by Formula function, and the label-audit agreement matrix."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features.formula import parse
from src.models.label_audit import LABELS
from src.utils.paths import FIGURES

INK, MUTED, GRID = "#1c1b19", "#52514e", "#e4e3df"
COL = {"verified": "#1b7a52", "concept": "#d08a1c", "illustrative": "#9a9893"}
NAME = {"verified": "Confirmed in Seeq docs", "concept": "Idea confirmed, syntax unverified", "illustrative": "Illustrative"}


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_axisbelow(True)


def funnel(f: dict, counts: dict):
    stages = [("Resource pages in sitemap (Sep 2026)", 424), ("Tracked: use cases + success stories", f["tracked"]),
              ("Extracted to the research Doc", f["extracted"]), ("NotebookLM notebooks", f["notebooks"]),
              ("Year-1 decks", f["decks"]), ("Step-by-step walkthroughs", f["walkthroughs"])]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    y = np.arange(len(stages))[::-1]
    ax.barh(y, [v for _, v in stages], color=["#9a9893"] + ["#2a5bd7"] * 5, height=0.62)
    for yi, (lab, v) in zip(y, stages):
        ax.text(v + 6, yi, f"{v}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [s for s, _ in stages], fontsize=9)
    ax.set_xlim(0, 480)
    ax.xaxis.set_visible(False)
    _style(ax)
    ax.spines["bottom"].set_visible(False)
    ax.set_title("From Seeq's public resource pages to walkthroughs", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "pipeline_funnel.png")
    plt.close(fig)


def labels_by_function(steps: pd.DataFrame, top=12):
    rows = []
    for r in steps.itertuples():
        p = parse(r.formula)
        names = sorted({c.name for c in p.calls}) if p.calls else (["(arithmetic only)"] if p.is_formula else ["(not Formula)"])
        rows += [dict(fn=n, label=r.label) for n in names]
    d = pd.crosstab(pd.DataFrame(rows).fn, pd.DataFrame(rows).label).reindex(columns=LABELS, fill_value=0)
    d = d.loc[d.sum(axis=1).sort_values(ascending=False).index[:top]][::-1]
    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=150)
    left = np.zeros(len(d))
    for lab in LABELS:
        ax.barh(d.index, d[lab], left=left, color=COL[lab], label=NAME[lab], height=0.62)
        left += d[lab].values
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(axis="x", color=GRID)
    _style(ax)
    ax.set_xlabel("Formula expressions using it", fontsize=9, color=MUTED)
    ax.set_title("Check label by Formula function (262 expressions, 78 walkthroughs)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "labels_by_function.png")
    plt.close(fig)


def agreement(summary: dict):
    cm = pd.DataFrame(summary["confusion"]).T.reindex(index=LABELS, columns=LABELS)
    fig, ax = plt.subplots(figsize=(5.2, 4), dpi=150)
    ax.imshow(cm.values, cmap="Blues")
    for i in range(3):
        for j in range(3):
            v = cm.values[i, j]
            ax.text(j, i, v, ha="center", va="center", color="white" if v > 60 else INK, fontsize=11)
    ax.set_xticks(range(3), LABELS, fontsize=9)
    ax.set_yticks(range(3), LABELS, fontsize=9)
    ax.set_xlabel("Label from the audit rules", fontsize=9)
    ax.set_ylabel("Label recorded in the walkthrough", fontsize=9)
    ax.set_title(f"Audit agrees on {summary['agreement']:.0%} of expressions", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "label_audit.png")
    plt.close(fig)
