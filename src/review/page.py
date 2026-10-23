"""Stage 4, publish: one self-contained HTML review page, a card per walkthrough grouped by industry.
Each card shows the problem, the solution idea, every build step with its Seeq tool, and each Formula expression
with its check label. 'Reviewed' ticks and notes are kept in the reader's browser only."""
from __future__ import annotations

import html
from collections import defaultdict

from src.models.label_audit import CHK

CSS = """:root{--bg:#fbfaf7;--card:#fff;--ink:#1c1b19;--ink2:#52514e;--line:#e4e3df;--good:#1b7a52;--amber:#a15c00;--muted:#7a7975;--accent:#2a5bd7}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#eceae4;--ink2:#b9b7b0;--line:#34332f;--good:#5cc596;--amber:#e3a548;--muted:#8d8b85;--accent:#8fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.sub{color:var(--ink2);margin:0 0 16px}.toc{columns:2 260px;font-size:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}
.card h3{margin:0 0 6px;font-size:16px}.card p{margin:6px 0;color:var(--ink2)}ol{padding-left:20px}li{margin:6px 0}
.tool{font:12px ui-monospace,monospace;color:var(--accent)}code{font:12.5px ui-monospace,monospace;background:var(--bg);padding:2px 6px;border-radius:5px;overflow-wrap:anywhere}
.chk{font:10.5px ui-monospace,monospace;text-transform:uppercase;border:1px solid currentColor;border-radius:5px;padding:1px 5px;margin-left:6px}
.verified{color:var(--good)}.concept{color:var(--amber)}.illustrative{color:var(--muted)}
.rev{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap}.rev textarea{flex:1;min-width:200px;font:inherit;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);padding:6px}
a{color:var(--accent)}"""

JS = """const KEY='seeq-review-v1';let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){st={}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
document.querySelectorAll('[data-id]').forEach(c=>{const id=c.dataset.id,cb=c.querySelector('input'),ta=c.querySelector('textarea');
const s=st[id]||{};cb.checked=!!s.r;ta.value=s.n||'';cb.onchange=()=>{st[id]={...st[id],r:cb.checked};save()};ta.oninput=()=>{st[id]={...st[id],n:ta.value};save()}});"""


def _e(x) -> str:
    return html.escape(str(x or ""))


def card(c: dict) -> str:
    steps = "".join(
        f"<li><span class='tool'>{_e(s['tool'])}</span> {_e(s['settings'])}"
        + (f"<br><code>{_e(s['formula'])}</code><span class='chk {s['check']}'>{CHK[s['check']]}</span>"
           if s.get("formula") else "")
        + "</li>" for s in c["steps"])
    problem = " ".join(c["problem"]) if isinstance(c["problem"], list) else c["problem"]
    return (f"<article class='card' id='{_e(c['id'])}' data-id='{_e(c['id'])}'><h3>{_e(c['title'])}</h3>"
            f"<p><b>Problem.</b> {_e(problem)}</p><p><b>Solution.</b> {_e(c['solution'])}</p>"
            f"<ol>{steps}</ol><p><a href='{_e(c['seeqUrl'])}'>Seeq use case page</a></p>"
            f"<div class='rev'><label><input type='checkbox'> Reviewed</label>"
            f"<textarea rows='1' placeholder='Notes for the next round'></textarea></div></article>")


def build(walkthroughs: dict, counts: dict | None = None) -> str:
    groups = defaultdict(list)
    for c in walkthroughs["cases"]:
        groups[c["industry"]].append(c)
    order = sorted(groups, key=lambda k: (-len(groups[k]), k))
    toc = "".join(f"<li><a href='#g{i}'>{_e(k)}</a> ({len(groups[k])})</li>" for i, k in enumerate(order))
    body = "".join(f"<h2 id='g{i}'>{_e(k)}</h2>" + "".join(card(c) for c in groups[k]) for i, k in enumerate(order))
    n_steps = sum(len(c["steps"]) for c in walkthroughs["cases"])
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>Seeq Use Case Review</title><style>{CSS}</style></head>"
            f"<body><main><h1>Seeq use case walkthroughs</h1><p class='sub'>{len(walkthroughs['cases'])} walkthroughs, "
            f"{n_steps} build steps. Written in our own words from public Seeq pages; each Formula expression carries "
            f"its check label. {_e(walkthroughs.get('method', ''))}</p><ul class='toc'>{toc}</ul>{body}</main>"
            f"<script>{JS}</script></body></html>")
