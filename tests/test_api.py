from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini import IncompleteModelResponseError


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


def test_text_only_input_does_not_require_image(monkeypatch) -> None:
    class Result:
        fingerprint = __import__("app.models", fromlist=["ProductFingerprint"]).ProductFingerprint(
            product_name="New Moon Konjac Noodle"
        )
        candidates = []
        sources = []
        trace = __import__("app.models", fromlist=["AgentTrace"]).AgentTrace(
            status="insufficient_evidence",
            iterations=1,
            tools_used=[],
            evidence_confidence_score=20,
            evidence_confidence_level="Low",
            steps=[],
        )

    monkeypatch.setattr("app.main.verification_agent.run", lambda *_args, **_kwargs: Result())
    response = client.post(
        "/api/analyze",
        data={"query": "New Moon Low Calorie Konjac Noodle 270g"},
    )
    assert response.status_code == 200


def test_incomplete_gemini_json_returns_friendly_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.verification_agent.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            IncompleteModelResponseError("Unterminated string at line 2")
        ),
    )
    response = client.post("/api/analyze", data={"query": "New Moon Konjac Noodle"})
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Gemini returned an incomplete comparison. Please retry the check."
    )


def test_upstream_timeout_returns_friendly_json_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.verification_agent.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("upstream request timeout")
        ),
    )
    response = client.post("/api/analyze", data={"query": "New Moon Konjac Noodle"})
    assert response.status_code == 504
    assert "took too long" in response.json()["detail"]

