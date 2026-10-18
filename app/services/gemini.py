from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from google import genai
from google.genai import types

from app.config import settings
from app.models import Candidate, ProductFingerprint, Source

logger = logging.getLogger(__name__)

ALLOWED_MARKETPLACES = {
    "shopee.sg": "Shopee",
    "lazada.sg": "Lazada",
    "www.lazada.sg": "Lazada",
    "shop.tiktok.com": "TikTok Shop",
    "amazon.sg": "Amazon SG",
    "www.amazon.sg": "Amazon SG",
    "courts.com.sg": "COURTS",
    "www.courts.com.sg": "COURTS",
    "challenger.sg": "Challenger",
    "www.challenger.sg": "Challenger",
}


def _json_payload(text: str) -> Any:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    return json.loads(cleaned)


def _client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.location,
        http_options=types.HttpOptions(api_version="v1"),
    )


def extract_fingerprint(
    query: str, image_bytes: bytes | None = None, mime_type: str | None = None
) -> ProductFingerprint:
    prompt = f"""
You are ShopProof, a precise product identity analyst for Singapore shoppers.
Extract a normalized product fingerprint from the user's text/URL and optional screenshot.
Never invent a model number, seller, variant, promotion, or price. Use null when not visible.
Return JSON only with these keys:
product_name, brand, model_number, variant, colour, storage, bundle,
source_marketplace, source_seller, visible_price, currency, search_terms, ambiguities.
visible_price must be numeric without currency symbols. currency defaults to SGD.
search_terms should contain 1-3 highly specific Singapore web searches, prioritizing exact model numbers.

User input: {query or 'Use the attached screenshot.'}
"""
    contents: list[Any] = [prompt]
    if image_bytes and mime_type:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    response = _client().models.generate_content(
        model=settings.model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return ProductFingerprint.model_validate(_json_payload(response.text))


def _extract_sources(response: Any) -> list[Source]:
    found: dict[str, Source] = {}
    for candidate in getattr(response, "candidates", []) or []:
        metadata = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", []) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            if uri and uri.startswith("http"):
                found[uri] = Source(title=getattr(web, "title", None) or "Web source", url=uri)
    return list(found.values())


def search_candidates(fingerprint: ProductFingerprint) -> tuple[list[Candidate], list[Source]]:
    identity = fingerprint.model_dump_json(exclude_none=True)
    prompt = f"""
You are a shopping verification agent. Search the public web for Singapore listings matching this product:
{identity}

Search Shopee Singapore, Lazada Singapore, TikTok Shop, and major Singapore retailers.
Return up to 8 useful listings from at least 2 platforms when available.
Do not treat accessories, refurbished goods, different model numbers, storage sizes, bundles, or generations as exact matches.
Only report prices and promotions visible in the search evidence. Never invent missing values.
Return JSON only as an array of objects with keys:
title, url, marketplace, seller, visible_price, currency, promotion, brand,
model_number, variant, colour, storage, bundle, evidence.
Each evidence value must be a short array of observed matching or conflicting facts.
"""
    response = _client().models.generate_content(
        model=settings.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=1.0,
        ),
    )
    sources = _extract_sources(response)
    raw = _json_payload(response.text)
    candidates: list[Candidate] = []
    for item in raw if isinstance(raw, list) else raw.get("candidates", []):
        try:
            candidate = Candidate.model_validate(item)
            host = urlparse(candidate.url).netloc.lower()
            if host in ALLOWED_MARKETPLACES:
                candidate.marketplace = ALLOWED_MARKETPLACES[host]
                candidates.append(candidate)
        except Exception as exc:  # individual noisy search results should not fail the run
            logger.info("Skipping malformed grounded result: %s", exc)
    return candidates, sources

