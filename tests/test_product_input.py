from app.services.product_input import parse_product_input


def test_parse_shopee_product_url() -> None:
    parsed = parse_product_input(
        "https://shopee.sg/Pro-60-Earphones-TWS-Wireless-Bluetooth-Headphones-"
        "9D-Stereo-Earbuds-i.1006220784.22544910928?extraParams=x"
    )

    assert parsed.marketplace == "Shopee"
    assert parsed.shop_id == "1006220784"
    assert parsed.item_id == "22544910928"
    assert parsed.slug_title == "Pro 60 Earphones TWS Wireless Bluetooth Headphones 9D Stereo Earbuds"


def test_plain_product_name_is_preserved() -> None:
    parsed = parse_product_input("Sony WH-1000XM5 Black Singapore")

    assert parsed.original == "Sony WH-1000XM5 Black Singapore"
    assert parsed.url is None
