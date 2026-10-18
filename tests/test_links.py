from app.services.gemini import _host_matches, _is_product_page


def test_marketplace_host_validation() -> None:
    assert _host_matches("https://www.lazada.sg/products/example.html", "Lazada")
    assert _host_matches("https://shopee.sg/example-i.1.2", "Shopee")
    assert not _host_matches("https://example.com/lazada.sg/product", "Lazada")


def test_lazada_requires_direct_product_page() -> None:
    assert _is_product_page(
        "https://www.lazada.sg/products/example-product-i123456.html", "Lazada"
    )
    assert not _is_product_page("https://www.lazada.sg/", "Lazada")
    assert not _is_product_page(
        "https://www.lazada.sg/shop/new-moon-official-store/", "Lazada"
    )


def test_shopee_requires_direct_product_page() -> None:
    assert _is_product_page("https://shopee.sg/example-i.123.456", "Shopee")
    assert not _is_product_page("https://shopee.sg/newmoonsg", "Shopee")
