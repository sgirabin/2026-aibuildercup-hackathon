from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.models import Candidate, ProductFingerprint


def normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _same(left: str | None, right: str | None) -> bool | None:
    if not left or not right:
        return None
    return normalize(left) == normalize(right)


def score_candidate(source: ProductFingerprint, candidate: Candidate) -> Candidate:
    score = 0
    decisive_mismatch = False

    model_match = _same(source.model_number, candidate.model_number)
    if model_match is True:
        score += 60
    elif model_match is False:
        decisive_mismatch = True

    brand_match = _same(source.brand, candidate.brand)
    if brand_match is True:
        score += 15
    elif brand_match is False:
        decisive_mismatch = True

    for source_value, candidate_value, weight in (
        (source.variant, candidate.variant, 7),
        (source.colour, candidate.colour, 4),
        (source.storage, candidate.storage, 6),
        (source.bundle, candidate.bundle, 3),
    ):
        result = _same(source_value, candidate_value)
        if result is True:
            score += weight
        elif result is False and weight >= 6:
            decisive_mismatch = True

    title_similarity = SequenceMatcher(
        None, normalize(source.product_name), normalize(candidate.title)
    ).ratio()
    score += round(title_similarity * 5)

    if not source.model_number and not candidate.model_number:
        score = min(85, score + round(title_similarity * 45))

    candidate.product_match_score = max(0, min(100, score))
    if decisive_mismatch or score < 55:
        candidate.verdict = "Variant mismatch"
    elif score >= 80:
        candidate.verdict = "Strong match"
    else:
        candidate.verdict = "Possible match"

    if source.source_seller and candidate.seller:
        seller_ratio = SequenceMatcher(
            None, normalize(source.source_seller), normalize(candidate.seller)
        ).ratio()
        candidate.seller_match_score = round(seller_ratio * 100)

    if source.visible_price is not None and candidate.visible_price is not None:
        candidate.savings = round(source.visible_price - candidate.visible_price, 2)

    return candidate


def rank_candidates(
    source: ProductFingerprint, candidates: list[Candidate]
) -> list[Candidate]:
    scored = [score_candidate(source, candidate) for candidate in candidates]
    return sorted(
        scored,
        key=lambda item: (
            item.verdict == "Strong match",
            item.product_match_score,
            item.savings if item.savings is not None else -10_000,
        ),
        reverse=True,
    )

