"""Load the tracker snapshot, the walkthrough store and the sitemap snapshot."""
import json

import pandas as pd

from src.utils.paths import DATA_RAW

SITEMAPS = DATA_RAW / "sitemaps"


def load_tracker() -> pd.DataFrame:
    """The Google Sheets tracker (one row per Seeq resource), exported; private notebook links removed."""
    return pd.read_csv(DATA_RAW / "tracker_snapshot.csv")


def load_walkthroughs() -> dict:
    """78 step-by-step walkthroughs, one per use case, as published on the review page."""
    return json.loads((DATA_RAW / "walkthroughs.json").read_text(encoding="utf-8"))


def load_sitemap(name: str) -> str:
    return (SITEMAPS / f"{name}-sitemap.xml").read_text(encoding="utf-8")


def load_section_counts() -> dict:
    return json.loads((SITEMAPS / "section_counts.json").read_text())


def formula_steps(walkthroughs: dict) -> pd.DataFrame:
    """One row per walkthrough step that carries a Formula check label."""
    rows = []
    for c in walkthroughs["cases"]:
        for i, s in enumerate(c["steps"]):
            if "check" in s:
                rows.append(dict(case_id=c["id"], case_title=c["title"], step=i + 1, tool=s["tool"],
                                 formula=s.get("formula") or "", label=s["check"]))
    return pd.DataFrame(rows)
