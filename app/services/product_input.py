from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


@dataclass(frozen=True)
class ProductInput:
    original: str
    url: str | None = None
    marketplace: str | None = None
    slug_title: str | None = None
    shop_id: str | None = None
    item_id: str | None = None

    def prompt_context(self) -> str:
        facts = [f"Original shopper input: {self.original}"]
        if self.url:
            facts.append(f"Product URL: {self.url}")
        if self.marketplace:
            facts.append(f"Marketplace inferred from URL: {self.marketplace}")
        if self.slug_title:
            facts.append(f"Product title inferred from URL slug: {self.slug_title}")
        if self.shop_id:
            facts.append(f"Marketplace shop ID: {self.shop_id}")
        if self.item_id:
            facts.append(f"Marketplace item ID: {self.item_id}")
        return "\n".join(facts)


def _slug_to_title(slug: str) -> str | None:
    slug = unquote(slug).strip("/-")
    if not slug:
        return None
    title = re.sub(r"[-_]+", " ", slug)
    title = re.sub(r"\s+", " ", title).strip()
    return title or None


def parse_product_input(value: str) -> ProductInput:
    match = URL_RE.search(value)
    if not match:
        return ProductInput(original=value)

    url = match.group(0).rstrip(".,;)")
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = unquote(parsed.path)

    marketplace: str | None = None
    slug_title: str | None = None
    shop_id: str | None = None
    item_id: str | None = None

    if host == "shopee.sg" or host.endswith(".shopee.sg"):
        marketplace = "Shopee"
        shopee_match = re.search(r"^(.*?)-i\.(\d+)\.(\d+)(?:/)?$", path.strip("/"))
        if shopee_match:
            slug_title = _slug_to_title(shopee_match.group(1))
            shop_id, item_id = shopee_match.group(2), shopee_match.group(3)
        else:
            slug_title = _slug_to_title(path.rsplit("/", 1)[-1])
    elif host == "lazada.sg" or host.endswith(".lazada.sg"):
        marketplace = "Lazada"
        slug_title = _slug_to_title(path.rsplit("/", 1)[-1].split(".html", 1)[0])
    elif host == "shop.tiktok.com" or host.endswith(".tiktok.com"):
        marketplace = "TikTok Shop"
        slug_title = _slug_to_title(path.rsplit("/", 1)[-1])

    return ProductInput(
        original=value,
        url=url,
        marketplace=marketplace,
        slug_title=slug_title,
        shop_id=shop_id,
        item_id=item_id,
    )
