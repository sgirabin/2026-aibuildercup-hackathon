from app.agent.kiasucheck_agent import KiasuCheckShoppingVerificationAgent
from app.models import Candidate, ProductFingerprint, Source


def fingerprint() -> ProductFingerprint:
    return ProductFingerprint(
        product_name="Sony WH-1000XM5 Black",
        brand="Sony",
        model_number="WH-1000XM5",
        colour="Black",
        source_marketplace="Shopee",
        visible_price=499,
        search_terms=["Sony WH-1000XM5 Singapore"],
    )


def supported_candidate() -> Candidate:
    return Candidate(
        title="Sony WH-1000XM5 Wireless Headphones Black",
        url="https://www.lazada.sg/products/example",
        marketplace="Lazada",
        brand="Sony",
        model_number="WH-1000XM5",
        colour="Black",
        visible_price=439,
        evidence=["Exact model visible", "Displayed price S$439"],
    )


def test_agent_refines_and_retries_when_evidence_is_empty(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.extract_fingerprint",
        lambda *_args, **_kwargs: fingerprint(),
    )

    def fake_search(fp, *_args, **_kwargs):
        calls.append(list(fp.search_terms))
        if len(calls) == 1:
            return [], []
        return [supported_candidate()], [Source(title="Lazada", url=supported_candidate().url)]

    monkeypatch.setattr("app.agent.kiasucheck_agent.search_candidates", fake_search)

    agent = KiasuCheckShoppingVerificationAgent()
    agent.max_iterations = 2
    result = agent.run(
        "Sony headphones", None, None, "exact", None, []
    )

    assert result.trace.iterations == 2
    assert result.trace.status == "completed"
    assert len(calls[1]) > len(calls[0])
    assert any("refined" in step.summary for step in result.trace.steps)
    assert result.candidates[0].verdict == "Strong match"


def test_agent_stops_after_first_sufficient_investigation(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.extract_fingerprint",
        lambda *_args, **_kwargs: fingerprint(),
    )
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.search_candidates",
        lambda *_args, **_kwargs: (
            [supported_candidate()],
            [Source(title="Lazada", url=supported_candidate().url)],
        ),
    )

    result = KiasuCheckShoppingVerificationAgent().run(
        "Sony headphones", None, None, "exact", None, []
    )

    assert result.trace.iterations == 1
    assert result.trace.evidence_confidence_score >= 60
    assert "google_search_grounding" in result.trace.tools_used


def test_same_shop_option_rejects_different_seller(monkeypatch) -> None:
    candidate = supported_candidate()
    candidate.match_type = "same_shop_product"
    candidate.seller = "Unrelated Marketplace Seller"
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.extract_fingerprint",
        lambda *_args, **_kwargs: fingerprint(),
    )
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.search_candidates",
        lambda *_args, **_kwargs: ([candidate], []),
    )

    result = KiasuCheckShoppingVerificationAgent().run(
        "Sony headphones", None, None, "seller", None, ["same_shop_product"]
    )
    assert result.candidates == []
    assert result.trace.status == "insufficient_evidence"


def test_selected_option_excludes_other_result_types(monkeypatch) -> None:
    candidate = supported_candidate()
    candidate.match_type = "similar_product"
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.extract_fingerprint",
        lambda *_args, **_kwargs: fingerprint(),
    )
    monkeypatch.setattr(
        "app.agent.kiasucheck_agent.search_candidates",
        lambda *_args, **_kwargs: ([candidate], []),
    )

    result = KiasuCheckShoppingVerificationAgent().run(
        "Sony headphones", None, None, "exact", None, ["same_product"]
    )
    assert result.candidates == []
