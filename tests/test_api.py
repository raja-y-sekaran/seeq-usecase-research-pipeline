from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_check_formula_known_and_unknown_syntax():
    r = client.post("/check-formula", json={"formula": "$flow.valueSearch(1day, isGreaterThan(0.5))"}).json()
    assert r["label"] == "verified" and r["seen_in"]
    r = client.post("/check-formula", json={"formula": "$flow.someNewFunction(5min)"}).json()
    assert r["label"] == "concept"


def test_cases():
    cs = client.get("/cases").json()
    assert len(cs) == 78
    c = client.get(f"/cases/{cs[0]['id']}").json()
    assert c["steps"] and "notebookUrl" not in c
    assert client.get("/cases/nope").status_code == 404
