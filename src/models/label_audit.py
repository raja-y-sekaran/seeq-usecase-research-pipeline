"""Audit the confirmed / concept / illustrative labels on the walkthrough Formula expressions.

The labels were set when each walkthrough was written: every expression was checked against the Seeq
Knowledge Base pages loaded into that use case's NotebookLM notebook.
    verified      'Confirmed in Seeq docs': the syntax was found in the KB
    concept       'Idea confirmed, syntax unverified'
    illustrative  placeholder values or not Formula at all

This module re-derives a label with simple rules and reports where the two disagree, as a review list.
It checks *consistency*, not truth: it cannot read the KB itself.

Rules
  R1  not Seeq Formula (Python SDK, empty)                          -> illustrative
  R2  uses calls, and every call shape was labelled verified in
      at least one OTHER walkthrough (leave-one-case-out registry)  -> verified, else concept
  R3  plain arithmetic on signals (no calls): the syntax is core Formula, so -> verified,
      unless the values look invented (bare placeholder names like a, b, or decimal coefficients
      such as 0.65 or 1.5 that a site would have to fit)            -> illustrative
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import pandas as pd

from src.features.formula import parse
from src.utils.paths import MODELS

LABELS = ["verified", "concept", "illustrative"]
CHK = {"verified": "Confirmed in Seeq docs", "concept": "Idea confirmed, syntax unverified",
       "illustrative": "Illustrative"}


def invented_values(p) -> list[str]:
    """Reasons to think an arithmetic expression's numbers are placeholders."""
    why = []
    toks = p.expression.replace("$", " $").split()
    bare = [t for t in pd.Series(toks).str.extract(r"^\(?([a-d])\b", expand=False).dropna()]
    if bare:
        why.append("placeholder coefficient names")
    decimals = [x for x in p.numbers if x != int(x)]
    if decimals:
        why.append("decimal coefficients " + ", ".join(f"{x:g}" for x in decimals[:3]))
    return why


def build_registry(steps: pd.DataFrame) -> dict:
    """shape -> {case_id: count} for shapes labelled verified."""
    reg = defaultdict(Counter)
    for r in steps.itertuples():
        if r.label == "verified":
            for s in parse(r.formula).shapes:
                reg[s][r.case_id] += 1
    return reg


def predict(formula: str, registry: dict, exclude_case: str | None = None) -> tuple[str, str]:
    p = parse(formula)
    if not p.is_formula:
        return "illustrative", "R1 not Seeq Formula"
    if p.calls:
        unknown = [s for s in p.shapes
                   if not any(c != exclude_case for c in registry.get(s, {}))]
        if unknown:
            return "concept", "R2 shape not confirmed elsewhere: " + ", ".join(unknown)
        return "verified", "R2 every call shape confirmed in another walkthrough"
    why = invented_values(p)
    return ("illustrative", "R3 " + "; ".join(why)) if why else ("verified", "R3 core arithmetic")


def audit(steps: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    reg = build_registry(steps)
    out = steps.copy()
    res = [predict(r.formula, reg, exclude_case=r.case_id) for r in steps.itertuples()]
    out["rule_label"] = [a for a, _ in res]
    out["rule_reason"] = [b for _, b in res]
    out["agrees"] = out.rule_label.eq(out.label)
    # shapes labelled differently in different walkthroughs: the most useful review items
    by_shape = defaultdict(Counter)
    for r in steps.itertuples():
        for s in parse(r.formula).shapes:
            by_shape[s][r.label] += 1
    mixed = {s: dict(c) for s, c in by_shape.items() if len(c) > 1}
    cm = pd.crosstab(out.label, out.rule_label).reindex(index=LABELS, columns=LABELS, fill_value=0)
    summary = dict(
        expressions=len(out), recorded=out.label.value_counts().reindex(LABELS, fill_value=0).to_dict(),
        agreement=round(float(out.agrees.mean()), 3), confusion=cm.to_dict(orient="index"),
        distinct_call_shapes=len(by_shape), shapes_with_mixed_labels=mixed,
        disagreements=int((~out.agrees).sum()))
    return out, summary


def save_registry(steps: pd.DataFrame):
    reg = build_registry(steps)
    (MODELS / "syntax_registry.json").write_text(json.dumps(
        {s: sorted(c) for s, c in sorted(reg.items())}, indent=1))
    (MODELS / "model_card.json").write_text(json.dumps(dict(
        model="Rule-based label audit for Seeq Formula expressions; no trained weights",
        registry="call shapes (function name + argument kinds) labelled 'Confirmed in Seeq docs' in the walkthroughs, "
                 "with the walkthroughs that use them",
        rules=["R1 not Seeq Formula -> illustrative",
               "R2 every call shape confirmed in another walkthrough -> verified, else concept",
               "R3 plain arithmetic -> verified unless placeholder names or decimal coefficients -> illustrative"],
        limits="checks consistency between walkthroughs, not correctness against the Seeq Knowledge Base; "
               "R3 cannot tell a physical constant (1.013 bar) from an invented weight",
    ), indent=2))
    return MODELS / "syntax_registry.json"
