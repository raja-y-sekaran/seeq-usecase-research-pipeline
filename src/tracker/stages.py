"""The tracker state machine that drove the five scheduled stages.

Gemini Spark schedules are stateless, so all state lives in one tracker sheet: each row is a Seeq resource and
each stage reads the rows waiting for it, processes a small capped batch and writes the result back. When
nothing is waiting a stage does nothing. This module is that logic, separated from the agents that did the
work (Gemini Spark, NotebookLM, and a browser agent), so it can be tested and simulated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str) == "False")


@dataclass(frozen=True)
class Stage:
    key: str
    name: str
    cap: int | None
    waiting: Callable[[pd.DataFrame], pd.Series]
    done_col: str
    done_value: object


STAGES = [
    Stage("extract", "1 Extract to Doc", 10, lambda t: t["Extract Status"].eq("Pending"), "Extract Status", "Done"),
    Stage("notebook", "2 Build notebooks", 3,
          lambda t: t.Section.eq("Use Cases") & t["Extract Status"].eq("Done") & _blank(t["Has Notebook"]),
          "Has Notebook", True),
    Stage("deck", "3 Generate decks", 3,
          lambda t: t["Has Notebook"].eq(True) & _blank(t["Deck Status"]), "Deck Status", "Done"),
    Stage("publish", "4 Publish review page", None,
          lambda t: t["Deck Status"].eq("Done") & _blank(t["Published"]), "Published", "Yes"),
    Stage("walkthrough", "5 Walkthrough (added Oct 2026)", 10,
          lambda t: t["Has Notebook"].eq(True) & _blank(t["Walkthrough Status"]), "Walkthrough Status", "Done"),
]
BY_KEY = {s.key: s for s in STAGES}


def select_batch(tracker: pd.DataFrame, stage: str) -> pd.Index:
    """Rows this stage would pick on its next run, newest first, capped. Empty means: do nothing."""
    s = BY_KEY[stage]
    idx = tracker.index[s.waiting(tracker)]
    if "Date Found" in tracker:
        idx = tracker.loc[idx].sort_values("Date Found", ascending=False, kind="stable").index
    return idx if s.cap is None else idx[: s.cap]


def apply(tracker: pd.DataFrame, stage: str, rows: pd.Index, ok: Callable[[pd.Series], bool] = lambda r: True):
    """Write a stage's result back: done value on success, 'Failed' on the status column otherwise."""
    s = BY_KEY[stage]
    t = tracker.copy()
    for i in rows:
        if ok(t.loc[i]):
            t.loc[i, s.done_col] = s.done_value
        elif t[s.done_col].dtype == object:
            t.loc[i, s.done_col] = "Failed"
    return t


def run_day(tracker: pd.DataFrame, stages=("extract", "notebook", "deck", "publish"), ok=lambda r: True):
    """One day of the daily schedules, in their clock order. Returns (tracker, rows processed per stage)."""
    t, log = tracker, {}
    for st in stages:
        rows = select_batch(t, st)
        log[st] = len(rows)
        if len(rows):
            t = apply(t, st, rows, ok)
    return t, log


def simulate(tracker: pd.DataFrame, max_days=120, **kw) -> pd.DataFrame:
    """Run day after day until every stage is idle; one row per day with what each stage processed."""
    t, days = tracker, []
    for d in range(1, max_days + 1):
        t, log = run_day(t, **kw)
        if not any(log.values()):
            break
        days.append(dict(day=d, **log))
    return pd.DataFrame(days)


def funnel(tracker: pd.DataFrame) -> dict:
    t = tracker
    uc = t.Section.eq("Use Cases")
    return {"tracked": len(t), "use_cases": int(uc.sum()), "success_stories": int((~uc).sum()),
            "extracted": int(t["Extract Status"].eq("Done").sum()),
            "notebooks": int(t["Has Notebook"].eq(True).sum()), "decks": int(t["Deck Status"].eq("Done").sum()),
            "published": int(t.Published.eq("Yes").sum()),
            "walkthroughs": int(t["Walkthrough Status"].eq("Done").sum())}


def reset_for_simulation(tracker: pd.DataFrame) -> pd.DataFrame:
    """The seeded state: every row Pending, nothing built yet."""
    t = tracker[["Section", "Title", "URL", "Date Found"]].copy()
    t["Extract Status"] = "Pending"
    for c in ("Deck Status", "Published", "Walkthrough Status", "Notes"):
        t[c] = pd.NA
    t["Has Notebook"] = False
    return t
