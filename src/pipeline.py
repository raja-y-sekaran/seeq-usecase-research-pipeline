"""Stages wired together on the snapshots in data/raw/:
discovery diff -> tracker status and schedule simulation -> Formula label audit -> review page -> metrics."""
from __future__ import annotations

import json

from src.data.load_data import formula_steps, load_section_counts, load_sitemap, load_tracker, load_walkthroughs
from src.discovery.sitemap import discover, parse_sitemap
from src.models.label_audit import audit
from src.review.page import build
from src.tracker.stages import funnel, reset_for_simulation, simulate
from src.utils.paths import DATA_PROCESSED, REPORTS

SNAPSHOT_DATE = "2026-10-24"


def run():
    tracker, wt, counts = load_tracker(), load_walkthroughs(), load_section_counts()
    rows = parse_sitemap(load_sitemap("use-case")) + parse_sitemap(load_sitemap("success-story"))
    updated, disc = discover(rows, tracker, today=SNAPSHOT_DATE)
    updated.to_csv(DATA_PROCESSED / "tracker_after_discovery.csv", index=False)
    sim = simulate(reset_for_simulation(tracker))
    sim.to_csv(DATA_PROCESSED / "schedule_simulation.csv", index=False)
    steps = formula_steps(wt)
    audited, summary = audit(steps)
    audited.to_csv(DATA_PROCESSED / "formula_audit.csv", index=False)
    audited[~audited.agrees].to_csv(REPORTS / "label_review_list.csv", index=False)
    (REPORTS / "review_page.html").write_text(build(wt, counts), encoding="utf-8")
    f = funnel(tracker)
    metrics = dict(
        sitemap=dict(snapshot_date=counts["snapshot_date"], resource_pages=counts["resource_total"],
                     by_section=counts["resource_sections"], september_seed_pages=424),
        discovery=dict(new=[n["URL"] for n in disc["new"]], skipped=disc["skipped"], removed=disc["removed"]),
        tracker=f,
        walkthroughs=dict(cases=len(wt["cases"]), steps=sum(len(c["steps"]) for c in wt["cases"]),
                          formula_expressions=summary["expressions"]),
        schedule_simulation=dict(days_to_clear_backlog=int(len(sim)), caps=dict(extract=10, notebook=3, deck=3)),
        label_audit={k: v for k, v in summary.items()})
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics, tracker, steps, summary
