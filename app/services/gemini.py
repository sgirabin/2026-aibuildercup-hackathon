from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal
from urllib.parse import quote_plus, urlparse

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings
from app.models import Candidate, ProductFingerprint, SearchIntent, Source
from app.services.product_input import parse_product_input

logger = logging.getLogger(__name__)


class IncompleteModelResponseError(RuntimeError):
    """Gemini returned structured output that could not be decoded completely."""

ALLOWED_MARKETPLACES = {
    "shopee": "Shopee",
    "lazada": "Lazada",
    "tiktok shop": "TikTok Shop",
    "amazon sg": "Amazon SG",
    "amazon": "Amazon SG",
    "courts": "COURTS",
    "challenger": "Challenger",
}

MARKETPLACE_HOSTS = {
    "Shopee": ("shopee.sg",),
    "Lazada": ("lazada.sg",),
    "TikTok Shop": ("tiktok.com",),
    "Amazon SG": ("amazon.sg",),
    "COURTS": ("courts.com.sg",),
    "Challenger": ("challenger.sg",),
}


def _host_matches(url: str, marketplace: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in MARKETPLACE_HOSTS.get(marketplace, ()))


def _marketplace_search_url(marketplace: str, title: str) -> str:
    query = quote_plus(title)
    return {
        "Shopee": f"https://shopee.sg/search?keyword={query}",
        "Lazada": f"https://www.lazada.sg/catalog/?q={query}",
        "TikTok Shop": f"https://www.tiktok.com/search?q={query}",
        "Amazon SG": f"https://www.amazon.sg/s?k={query}",
        "COURTS": f"https://www.courts.com.sg/catalogsearch/result/?q={query}",
        "Challenger": f"https://www.challenger.sg/search?q={query}",
    }.get(marketplace, "https://www.google.com/search?q=" + query)


def _resolve_listing_url(listing: "FoundListing") -> str:
    """Turn a temporary grounding redirect into a durable marketplace URL.

    A marketplace search is safer than returning a dead product page, and still lets
    the shopper verify the exact title and seller shown by KiasuCheck.
    """
    is_direct_marketplace_url = _host_matches(listing.source_url, listing.marketplace)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(5.0),
            headers={"User-Agent": "Mozilla/5.0 KiasuCheck/0.6"},
        ) as client:
            with client.stream("GET", listing.source_url) as response:
                resolved = str(response.url)
                if response.status_code != 404 and _host_matches(resolved, listing.marketplace):
                    return resolved
    except (httpx.HTTPError, ValueError):
        logger.info("grounded_link_resolution_failed marketplace=%s", listing.marketplace)
        if is_direct_marketplace_url:
            return listing.source_url
    return _marketplace_search_url(listing.marketplace, listing.title)


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
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise IncompleteModelResponseError(
            "Gemini returned incomplete structured output."
        ) from exc


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
    listings = None
    for attempt in range(1, 3):
        started = time.perf_counter()
        with _client() as client:
            structured = client.models.generate_content(
                model=settings.model,
                contents=structure_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[FoundListing],
                    temperature=0.0,
                ),
            )
        logger.info(
            "gemini_structure_results elapsed_seconds=%.2f attempt=%d",
            time.perf_counter() - started,
            attempt,
        )
        try:
            listings = structured.parsed
            if not isinstance(listings, list):
                listings = [
                    FoundListing.model_validate(item)
                    for item in _json_payload(structured.text or "")
                ]
            break
        except IncompleteModelResponseError:
            if attempt == 2:
                raise
            logger.warning("gemini_structure_results incomplete; retrying once")

    if listings is None:
        raise IncompleteModelResponseError("Gemini returned no structured listings.")

    # Grounding citations can be temporary Google redirect URLs. Resolve the small
    # candidate set concurrently so links remain useful without materially extending
    # the comparison latency.
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(listings)))) as executor:
        resolved_urls = list(executor.map(_resolve_listing_url, listings))

    allowed_urls = {str(source.url) for source in sources}
    candidates: list[Candidate] = []
    for listing, resolved_url in zip(listings, resolved_urls):
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
                url=resolved_url,
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
