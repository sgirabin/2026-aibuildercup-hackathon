from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProductFingerprint(BaseModel):
    product_name: str
    brand: str | None = None
    model_number: str | None = None
    variant: str | None = None
    colour: str | None = None
    storage: str | None = None
    bundle: str | None = None
    source_marketplace: str | None = None
    source_seller: str | None = None
    visible_price: float | None = None
    currency: str = "SGD"
    search_terms: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    title: str
    url: str
    marketplace: str
    seller: str | None = None
    visible_price: float | None = None
    currency: str = "SGD"
    promotion: str | None = None
    brand: str | None = None
    model_number: str | None = None
    variant: str | None = None
    colour: str | None = None
    storage: str | None = None
    bundle: str | None = None
    evidence: list[str] = Field(default_factory=list)
    product_match_score: int = 0
    seller_match_score: int | None = None
    verdict: Literal["Strong match", "Possible match", "Variant mismatch"] = "Possible match"
    savings: float | None = None


class Source(BaseModel):
    title: str
    url: str


class AnalysisResponse(BaseModel):
    fingerprint: ProductFingerprint
    candidates: list[Candidate]
    sources: list[Source] = Field(default_factory=list)
    mode: Literal["live", "demo"]
    warning: str | None = None

