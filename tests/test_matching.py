from app.models import Candidate, ProductFingerprint
from app.services.matching import rank_candidates, score_candidate


def source() -> ProductFingerprint:
    return ProductFingerprint(
        product_name="Sony WH-1000XM5 Black",
        brand="Sony",
        model_number="WH-1000XM5",
        colour="Black",
        visible_price=499,
        source_seller="Audio Official",
    )


def test_exact_model_scores_as_strong_match() -> None:
    candidate = Candidate(
        title="Sony WH1000XM5 Wireless Headphones Black",
        url="https://shopee.sg/example",
        marketplace="Shopee",
        brand="SONY",
        model_number="WH1000XM5",
        colour="black",
        visible_price=439,
        seller="Audio-Official",
    )
    result = score_candidate(source(), candidate)
    assert result.verdict == "Strong match"
    assert result.product_match_score >= 80
    assert result.seller_match_score == 100
    assert result.savings == 60
    assert result.evidence_confidence_score >= 60
    assert result.evidence_confidence_level in {"High", "Medium"}


def test_different_model_is_rejected_even_if_cheaper() -> None:
    candidate = Candidate(
        title="Sony WH-1000XM4 Black",
        url="https://shop.tiktok.com/example",
        marketplace="TikTok Shop",
        brand="Sony",
        model_number="WH-1000XM4",
        colour="Black",
        visible_price=299,
    )
    result = score_candidate(source(), candidate)
    assert result.verdict == "Variant mismatch"
    assert result.product_match_score < 55
    assert result.evidence_confidence_score <= 45
    assert result.evidence_confidence_level == "Low"


def test_ranking_prioritizes_identity_over_low_price() -> None:
    candidates = [
        Candidate(title="Sony XM4", url="https://example.com/xm4", marketplace="Other", brand="Sony", model_number="WH-1000XM4", visible_price=250),
        Candidate(title="Sony XM5", url="https://example.com/xm5", marketplace="Other", brand="Sony", model_number="WH-1000XM5", visible_price=450),
    ]
    ranked = rank_candidates(source(), candidates)
    assert ranked[0].model_number == "WH-1000XM5"

