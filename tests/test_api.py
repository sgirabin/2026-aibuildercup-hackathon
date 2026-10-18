from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model"]
    assert response.json()["version"]
    assert response.json()["git_commit"]
    assert response.json()["revision"]


def test_demo_analysis() -> None:
    response = client.post(
        "/api/analyze",
        data={"query": "Sony WH-1000XM5", "force_demo": "true"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    assert len(payload["candidates"]) >= 3
    assert payload["candidates"][0]["verdict"] == "Strong match"
    assert payload["agent"]["name"] == "KiasuCheck Shopping Verification Agent"
    assert payload["agent"]["evidence_confidence_level"] in {"High", "Medium", "Low"}


def test_rejects_empty_input() -> None:
    response = client.post("/api/analyze", data={"query": ""})
    assert response.status_code == 400

