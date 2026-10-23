import pandas as pd
import pytest

from src.discovery.sitemap import classify, discover, parse_sitemap
from src.features.formula import parse
from src.models.label_audit import predict
from src.tracker.stages import funnel, reset_for_simulation, select_batch, simulate


def test_parse_value_search_shape_and_units():
    p = parse("$flow.valueSearch(1day, isGreaterThan(0.5 m^3/h))")
    assert p.refs == ["$flow"]
    assert p.shapes == ["isGreaterThan(num)", "valueSearch(dur,call)"]
    assert p.durations == ["1day"]


def test_parse_strings_and_nested_calls():
    p = parse("$batchState.valueSearch(1d, isEqualTo('HEAT')).removeShorterThan(5min)")
    assert set(p.shapes) == {"valueSearch(dur,call)", "isEqualTo(str)", "removeShorterThan(dur)"}
    assert p.strings == ["'HEAT'"]


def test_python_sdk_is_not_formula():
    assert not parse("spy.search({'Path': 'Area 1'})").is_formula
    assert not parse("").is_formula


@pytest.mark.parametrize("url,section", [
    ("https://www.seeq.com/resources/use-cases/pump-health-monitoring/", "Use Cases"),
    ("https://www.seeq.com/resources/use-cases/induced-draft-fan-maintenance/", "Use Cases"),
    ("https://www.seeq.com/resources/use-cases/minimize-vented-steam-in-dual-boiler-system-draft/", None),
    ("https://www.seeq.com/wp-content/uploads/2026/08/SB_Top-5-Use-Cases-for-FB.pdf#new_tab", None),
    ("https://www.seeq.com/resources/success-stories/some-story/", "Success Stories"),
])
def test_classify_rules_from_the_real_sitemap(url, section):
    assert classify(url)[0] == section


XML = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.seeq.com/resources/use-cases/a/</loc></url>
<url><loc>https://www.seeq.com/resources/use-cases/b/</loc><lastmod>2026-10-01T00:00:00+00:00</lastmod></url>
</urlset>"""


def test_discover_adds_new_and_flags_removed_without_deleting():
    t = pd.DataFrame([dict(Section="Use Cases", Title="A", URL="https://www.seeq.com/resources/use-cases/a/",
                           Notes=None, **{"Extract Status": "Done"}),
                      dict(Section="Use Cases", Title="Old", URL="https://www.seeq.com/resources/use-cases/old/",
                           Notes=None, **{"Extract Status": "Done"})])
    out, r = discover(parse_sitemap(XML), t, today="2026-10-24")
    assert [n["Title"] for n in r["new"]] == ["B"] and r["new"][0]["Publish Date"] == "2026-10-01"
    assert len(out) == 3 and out.loc[1, "Notes"] == "Removed from site"
    out2, r2 = discover(parse_sitemap(XML), out, today="2026-10-25")
    assert r2["new"] == [] and len(out2) == 3      # idempotent


def _seed(n_use=7, n_story=2):
    rows = [dict(Section="Use Cases", Title=f"U{i}", URL=f"u{i}", **{"Date Found": "2026-09-25"}) for i in range(n_use)]
    rows += [dict(Section="Success Stories", Title=f"S{i}", URL=f"s{i}", **{"Date Found": "2026-09-25"})
             for i in range(n_story)]
    return reset_for_simulation(pd.DataFrame(rows))


def test_stage_caps_and_idle():
    t = _seed()
    assert len(select_batch(t, "extract")) == 9 and len(select_batch(t, "notebook")) == 0
    sim = simulate(t)
    assert sim.notebook.max() == 3 and sim.notebook.sum() == 7      # success stories get no notebook
    assert len(sim) == 3            # 3 + 3 + 1 notebooks; decks run later the same day (clock order)
    assert sim.extract.sum() == 9 and sim.publish.sum() == 7


def test_funnel_counts_real_snapshot():
    from src.data.load_data import load_tracker
    f = funnel(load_tracker())
    assert (f["tracked"], f["use_cases"], f["success_stories"], f["walkthroughs"]) == (100, 83, 17, 78)


REG = {"valueSearch(dur,call)": {"case-a": 1}, "isGreaterThan(num)": {"case-a": 1, "case-b": 1}}


def test_predict_rules():
    f = "$x.valueSearch(1d, isGreaterThan(3))"
    assert predict(f, REG)[0] == "verified"
    assert predict(f, REG, exclude_case="case-a")[0] == "concept"     # leave-one-case-out
    assert predict("$x.agileFilter(15min)", REG)[0] == "concept"
    assert predict("$a - $b", REG)[0] == "verified"
    assert predict("$kilnFeed * 0.65", REG)[0] == "illustrative"
    assert predict("spy.search({'Name': 'x'})", REG)[0] == "illustrative"
