from __future__ import annotations

from app.models import Candidate, ProductFingerprint


DEMO_CATALOGUE = {
    "sony": {
        "fingerprint": ProductFingerprint(
            product_name="Sony WH-1000XM5 Wireless Headphones",
            brand="Sony",
            model_number="WH-1000XM5",
            variant="International set",
            colour="Black",
            source_marketplace="Shopee",
            source_seller="Audio Official",
            visible_price=499.0,
            search_terms=["Sony WH-1000XM5 Black Singapore"],
        ),
        "candidates": [
            Candidate(title="Sony WH-1000XM5 Black", url="https://www.lazada.sg/", marketplace="Lazada", seller="Sony Store", visible_price=439.0, promotion="$20 voucher", brand="Sony", model_number="WH-1000XM5", colour="Black", variant="International set", evidence=["Model number and colour match"]),
            Candidate(title="Sony WH-1000XM5 Wireless Headphones", url="https://shopee.sg/", marketplace="Shopee", seller="Audio Official", visible_price=459.0, promotion="8% platform voucher", brand="Sony", model_number="WH-1000XM5", colour="Black", variant="International set", evidence=["Seller name and model match"]),
            Candidate(title="Sony WH-1000XM4 Headphones", url="https://shop.tiktok.com/", marketplace="TikTok Shop", seller="Gadget Planet", visible_price=329.0, brand="Sony", model_number="WH-1000XM4", colour="Black", evidence=["Different model: XM4, not XM5"]),
        ],
    },
    "nintendo": {
        "fingerprint": ProductFingerprint(
            product_name="Nintendo Switch OLED Console",
            brand="Nintendo",
            model_number="HEG-001",
            variant="OLED",
            colour="White",
            source_marketplace="Lazada",
            visible_price=479.0,
            search_terms=["Nintendo Switch OLED HEG-001 White Singapore"],
        ),
        "candidates": [
            Candidate(title="Nintendo Switch OLED White HEG-001", url="https://shopee.sg/", marketplace="Shopee", seller="GameMart SG", visible_price=409.0, promotion="$12 voucher", brand="Nintendo", model_number="HEG-001", variant="OLED", colour="White", evidence=["Exact hardware revision match"]),
            Candidate(title="Nintendo Switch OLED Neon", url="https://www.lazada.sg/", marketplace="Lazada", seller="Console World", visible_price=419.0, brand="Nintendo", model_number="HEG-001", variant="OLED", colour="Neon", evidence=["Same console, different colour"]),
            Candidate(title="Nintendo Switch V2 Console", url="https://shop.tiktok.com/", marketplace="TikTok Shop", seller="Play Hub", visible_price=319.0, brand="Nintendo", model_number="HAC-001", variant="V2", evidence=["Different non-OLED hardware model"]),
        ],
    },
}


def get_demo(query: str) -> tuple[ProductFingerprint, list[Candidate]]:
    key = "nintendo" if "nintendo" in query.lower() or "switch" in query.lower() else "sony"
    item = DEMO_CATALOGUE[key]
    return item["fingerprint"].model_copy(deep=True), [candidate.model_copy(deep=True) for candidate in item["candidates"]]

