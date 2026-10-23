"""FastAPI service: check a Seeq Formula expression against the walkthroughs' confirmed syntax, and look up cases.

    uvicorn src.api.app:app --reload      # then open http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.data.load_data import formula_steps, load_walkthroughs
from src.features.formula import ParseError, parse
from src.models.label_audit import CHK, build_registry, predict

app = FastAPI(title="Seeq use case research pipeline", version="1.0",
              description="Label audit and walkthrough lookup. Built on public Seeq pages; not affiliated with Seeq.")
_WT = load_walkthroughs()
_REG = build_registry(formula_steps(_WT))
_CASES = {c["id"]: c for c in _WT["cases"]}


class Expression(BaseModel):
    formula: str = Field(examples=["$flow.valueSearch(1day, isGreaterThan(0.5))"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check-formula")
def check_formula(e: Expression):
    try:
        p = parse(e.formula)
    except ParseError as err:
        raise HTTPException(422, str(err)) from err
    label, reason = predict(e.formula, _REG)
    return dict(label=label, meaning=CHK[label], reason=reason, signals=p.refs, call_shapes=p.shapes,
                seen_in=sorted({c for s in p.shapes for c in _REG.get(s, {})})[:10])


@app.get("/cases")
def cases():
    return [dict(id=c["id"], title=c["title"], industry=c["industry"], steps=len(c["steps"])) for c in _WT["cases"]]


@app.get("/cases/{case_id}")
def case(case_id: str):
    if case_id not in _CASES:
        raise HTTPException(404, "unknown case")
    return _CASES[case_id]
