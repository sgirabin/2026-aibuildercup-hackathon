from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal
from urllib.parse import urlparse

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings
from app.models import Candidate, ProductFingerprint, SearchIntent, Source
from app.services.product_input import parse_product_input

logger = logging.getLogger(__name__)

ALLOWED_MARKETPLACES = {
    "shopee": "Shopee",
    "lazada": "Lazada",
    "tiktok shop": "TikTok Shop",
    "amazon sg": "Amazon SG",
    "amazon": "Amazon SG",
    "courts": "COURTS",
    "challenger": "Challenger",
}


class FoundListing(BaseModel):
    title: str
    source_url: str
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
    match_type: Literal["same_shop_product", "same_product", "similar_product"]


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
    product_input = parse_product_input(query)
    prompt = f"""
You are KiasuCheck, a precise product identity analyst for Singapore shoppers.
Extract a normalized product fingerprint from the supplied text, marketplace URL facts,
page metadata, and optional screenshot. A marketplace URL might not be fetchable, so use
its decoded slug title and IDs as evidence. Never invent a model number, seller, variant,
promotion, or price. Use null when a fact is not visible. Currency defaults to SGD.
Treat literal placeholders such as "not detected", "unknown", and "unavailable" as null.
Create 1-3 highly specific Singapore web search terms, prioritizing exact model numbers.

{product_input.prompt_context()}
"""
    contents: list[Any] = [prompt]
    if image_bytes and mime_type:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    started = time.perf_counter()
    with _client() as client:
        response = client.models.generate_content(
            model=settings.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductFingerprint,
                temperature=0.1,
                max_output_tokens=700,
            ),
        )
    logger.info("gemini_fingerprint elapsed_seconds=%.2f", time.perf_counter() - started)
    fingerprint = response.parsed
    if not isinstance(fingerprint, ProductFingerprint):
        fingerprint = ProductFingerprint.model_validate(_json_payload(response.text))

    if product_input.marketplace and not fingerprint.source_marketplace:
        fingerprint.source_marketplace = product_input.marketplace
    if product_input.slug_title and (
        not fingerprint.product_name or fingerprint.product_name.lower().startswith("unknown")
    ):
        fingerprint.product_name = product_input.slug_title
    if product_input.slug_title and not fingerprint.search_terms:
        fingerprint.search_terms = [f"{product_input.slug_title} Singapore"]
    return fingerprint


def _extract_sources(response: Any) -> list[Source]:
    found: dict[str, Source] = {}
    for candidate in getattr(response, "candidates", []) or []:
        metadata = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", []) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            if uri and uri.startswith("http"):
                found[uri] = Source(
                    title=getattr(web, "title", None) or "Grounded web source", url=uri
                )
    for uri in re.findall(r"https?://[^\s)>\]}]+", response.text or ""):
        clean = uri.rstrip(".,;")
        found.setdefault(clean, Source(title=urlparse(clean).netloc, url=clean))
    return list(found.values())


def _search_instruction(
    fingerprint: ProductFingerprint,
    intent: SearchIntent,
    target_marketplaces: list[str],
    objectives: list[str],
) -> str:
    if not objectives:
        objectives = {
            "seller": ["same_shop_product"],
            "similar": ["similar_product"],
            "exact": ["same_product"],
            "multi": ["same_product"],
        }[intent]

    instructions: list[str] = []
    if "same_shop_product" in objectives:
        instructions.append(
            "Find the same product sold by the same source shop on another platform; require "
            "evidence for both product identity and seller identity."
        )
    if "same_product" in objectives:
        instructions.append(
            "Find the exact same product from any seller and prioritize the cheapest supported price; "
            "reject different models, generations, sizes, bundles, and accessories."
        )
    if "similar_product" in objectives:
        instructions.append(
            "Find cheaper genuinely comparable products with similar purpose and specifications, and "
            "state the important differences."
        )
    targets = ", ".join(target_marketplaces)
    return " ".join(instructions) + f" Search only these target platforms: {targets}."


def search_candidates(
    fingerprint: ProductFingerprint,
    intent: SearchIntent = "exact",
    target_marketplace: str | None = None,
    objectives: list[str] | None = None,
) -> tuple[list[Candidate], list[Source]]:
    platform_names = ["Shopee", "Lazada", "TikTok Shop"]
    if target_marketplace:
        target_marketplaces = [target_marketplace]
    else:
        target_marketplaces = [
            platform
            for platform in platform_names
            if platform.lower() != (fingerprint.source_marketplace or "").lower()
        ]
    selected_objectives = objectives or []
    identity = fingerprint.model_dump_json(exclude_none=True)
    search_terms = "; ".join(fingerprint.search_terms)
    instruction = _search_instruction(
        fingerprint, intent, target_marketplaces, selected_objectives
    )
    prompt = f"""
You are KiasuCheck's web research agent. {instruction}

Product fingerprint:
{identity}

Preferred search terms: {search_terms}

Use Google Search and produce a concise evidence report of up to 8 useful Singapore offers.
For every offer, state the product title, marketplace, seller if visible, displayed SGD price,
promotion if visible, model or variant evidence, and the cited product-page source. Do not invent
prices, promotions, sellers, URLs, or unavailable product attributes. If the web evidence is sparse,
say so plainly. Prefer actual product pages over marketplace home pages.
"""
    started = time.perf_counter()
    with _client() as client:
        grounded = client.models.generate_content(
            model=settings.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=1.0,
                max_output_tokens=1800,
            ),
        )
        logger.info("gemini_grounded_search elapsed_seconds=%.2f", time.perf_counter() - started)
        sources = _extract_sources(grounded)
        if not sources:
            return [], []

    source_catalogue = "\n".join(
        f"[{index}] {source.title} | {source.url}"
        for index, source in enumerate(sources, start=1)
    )
    structure_prompt = f"""
Convert the grounded shopping report below into structured listings.

Rules:
- source_url must be copied exactly from the numbered source catalogue.
- Include only offers actually supported by the report and catalogue.
- Never fabricate a direct marketplace URL, price, seller, promotion, or attribute.
- Normalize marketplace to Shopee, Lazada, TikTok Shop, Amazon SG, COURTS, or Challenger.
- Use null for facts not present in evidence.
- evidence must contain short observed facts, including conflicts or uncertainty.
- visible_price must be a number without currency symbols.
- match_type must be same_shop_product, same_product, or similar_product and must match
  the evidence. same_shop_product requires both the product and seller to match.

Product to compare:
{identity}

Grounded report:
{grounded.text}

Numbered source catalogue:
{source_catalogue}
"""
    started = time.perf_counter()
    with _client() as client:
        structured = client.models.generate_content(
            model=settings.model,
            contents=structure_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[FoundListing],
                temperature=0.0,
                max_output_tokens=1800,
            ),
        )
    logger.info("gemini_structure_results elapsed_seconds=%.2f", time.perf_counter() - started)
    listings = structured.parsed
    if not isinstance(listings, list):
        listings = [FoundListing.model_validate(item) for item in _json_payload(structured.text)]

    allowed_urls = {str(source.url) for source in sources}
    candidates: list[Candidate] = []
    for listing in listings:
        if not isinstance(listing, FoundListing):
            listing = FoundListing.model_validate(listing)
        marketplace = ALLOWED_MARKETPLACES.get(listing.marketplace.strip().lower())
        if (
            not marketplace
            or marketplace not in target_marketplaces
            or listing.source_url not in allowed_urls
        ):
            continue
        candidates.append(
            Candidate(
                title=listing.title,
                url=listing.source_url,
                marketplace=marketplace,
                seller=listing.seller,
                visible_price=listing.visible_price,
                currency=listing.currency,
                promotion=listing.promotion,
                brand=listing.brand,
                model_number=listing.model_number,
                variant=listing.variant,
                colour=listing.colour,
                storage=listing.storage,
                bundle=listing.bundle,
                evidence=listing.evidence,
                match_type=listing.match_type,
            )
        )
    return candidates, sources
