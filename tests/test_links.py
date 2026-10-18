from app.services.gemini import _host_matches, _marketplace_search_url


def test_marketplace_host_validation() -> None:
    assert _host_matches("https://www.lazada.sg/products/example.html", "Lazada")
    assert _host_matches("https://shopee.sg/example-i.1.2", "Shopee")
    assert not _host_matches("https://example.com/lazada.sg/product", "Lazada")


def test_lazada_fallback_is_a_search_for_the_exact_title() -> None:
    url = _marketplace_search_url(
        "Lazada", "New Moon Low Calorie Konjac Noodle 270g"
    )
    assert url.startswith("https://www.lazada.sg/catalog/?q=")
    assert "New+Moon+Low+Calorie" in url


def test_shopee_fallback_is_a_search_for_the_exact_title() -> None:
    url = _marketplace_search_url("Shopee", "Sony WH-1000XM5 Black")
    assert url.startswith("https://shopee.sg/search?keyword=")
    assert "WH-1000XM5" in url
