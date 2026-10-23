"""Stage 0, discovery: read Seeq's public sitemaps and add any new resource page to the tracker as Pending.

Rules learned from the real sitemaps:
  * only pages under /resources/<section>/ count; file links (a PDF under /wp-content/, '#new_tab') are skipped
  * a slug ending in '-draft' is an unpublished copy of another page and is skipped
    (but 'induced-draft-fan-maintenance' is a real page, so the match is on the suffix only)
  * a URL already in the tracker is never added twice; a tracked URL missing from the sitemap is marked
    'Removed from site' in Notes, never deleted
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

import pandas as pd

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SECTIONS = {"use-cases": "Use Cases", "success-stories": "Success Stories", "blog": "Blog",
            "downloads": "Downloads", "events": "Events & Webinars", "webinars": "Events & Webinars",
            "videos": "Video Hub"}
TRACKER_COLUMNS = ["Section", "Title", "URL", "Date Found", "Publish Date", "Extract Status", "Deck Status",
                   "Published", "Notes", "Walkthrough Status", "Has Notebook", "Has Deck"]


def parse_sitemap(xml_text: str) -> list[tuple[str, str]]:
    root = ET.fromstring(xml_text)
    out = []
    for u in root.findall("sm:url", NS):
        loc = (u.findtext("sm:loc", default="", namespaces=NS) or "").strip()
        out.append((loc, (u.findtext("sm:lastmod", default="", namespaces=NS) or "")[:10]))
    return out


def classify(url: str) -> tuple[str | None, str]:
    """(section, reason). Section is None when the URL is not a resource page to track."""
    if "#" in url or re.search(r"\.(pdf|docx?|xlsx?|zip)$", url.split("#")[0], re.I) or "/wp-content/" in url:
        return None, "file link, not a page"
    m = re.search(r"/resources/([^/]+)/([^/]+)/?$", url)
    if not m:
        return None, "not under /resources/<section>/"
    section = SECTIONS.get(m.group(1))
    if section is None:
        return None, f"unknown section {m.group(1)}"
    if m.group(2).endswith("-draft"):
        return None, "draft copy of another page"
    return section, "ok"


def title_from_slug(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1].replace("-", " ")
    return slug[:1].upper() + slug[1:]


def discover(sitemap_rows: list[tuple[str, str]], tracker: pd.DataFrame, today: str | None = None,
             sections=("Use Cases", "Success Stories")):
    """Returns (updated tracker, report). Only `sections` are checked for removals (the sitemaps read)."""
    today = today or date.today().isoformat()
    tracked = set(tracker.URL)
    seen, new, skipped = set(), [], []
    for url, lastmod in sitemap_rows:
        section, why = classify(url)
        if section is None:
            skipped.append(dict(url=url, reason=why))
            continue
        seen.add(url)
        if url in tracked or url in {r["URL"] for r in new}:
            continue
        new.append({"Section": section, "Title": title_from_slug(url), "URL": url, "Date Found": today,
                    "Publish Date": lastmod, "Extract Status": "Pending"})
    t = tracker.copy()
    gone = t.Section.isin(sections) & ~t.URL.isin(seen)
    note = t.Notes.fillna("")
    t.loc[gone & ~note.str.contains("Removed from site"), "Notes"] = (note + " Removed from site").str.strip()
    removed = list(t.loc[gone, "URL"])
    if new:
        t = pd.concat([t, pd.DataFrame(new)], ignore_index=True)
    report = dict(pages_in_sitemap=len(sitemap_rows), tracked_pages_seen=len(seen & tracked), new=new,
                  skipped=skipped, removed=removed)
    return t, report
