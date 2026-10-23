"""Run the project end to end on the snapshots in data/raw/ (course layout).

    python main.py           # discovery diff, tracker status, schedule simulation, label audit, review page, figures
"""
import argparse
import json

from src import pipeline
from src.data.load_data import load_section_counts
from src.models.label_audit import save_registry
from src.utils import plots


def run_all(quiet=False):
    m, tracker, steps, summary = pipeline.run()
    plots.funnel(m["tracker"], load_section_counts())
    plots.labels_by_function(steps)
    plots.agreement(summary)
    save_registry(steps)
    if not quiet:
        print(json.dumps({k: m[k] for k in ("tracker", "walkthroughs", "schedule_simulation")}, indent=1))
        a = m["label_audit"]
        print(f"label audit: {a['agreement']:.0%} agreement on {a['expressions']} expressions, "
              f"{a['disagreements']} for review (reports/label_review_list.csv)")
        print("new on Seeq since the tracker was seeded:", m["discovery"]["new"])
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    run_all(ap.parse_args().quiet)
