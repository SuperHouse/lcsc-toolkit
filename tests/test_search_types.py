from lcsc_toolkit.search.types import Product


def _raw_product(**overrides):
    product = {
        "productCode": "C17179461",
        "productModel": "HY2005WV-N-2x8P",
        "productArrange": "Tape & Reel (TR)",
        "stockNumber": 1234,
        "productIntroEn": "Connector IDC Header Through Hole 16 position 2mm",
        "productImages": ["https://assets.lcsc.com/images/example.jpg"],
        "minBuyNumber": 5,
        "productPriceList": [
            {"ladder": 1, "discountPrice": 0.1335},
            {"ladder": 100, "discountPrice": 0.1002},
        ],
    }
    product.update(overrides)
    return product


def test_from_api_parses_core_fields():
    product = Product.from_api(_raw_product())

    assert product.product_code == "C17179461"
    assert product.product_model == "HY2005WV-N-2x8P"
    assert product.stock_number == 1234
    assert product.moq == 5


def test_from_api_parses_price_breaks():
    product = Product.from_api(_raw_product())

    assert [pb.quantity for pb in product.price_breaks] == [1, 100]
    assert product.price_breaks[0].price == 0.1335
    assert product.price_breaks[0].currency == "USD"


def test_from_api_skips_incomplete_price_break_rows():
    raw = _raw_product(
        productPriceList=[
            {"ladder": 1, "discountPrice": 0.5},
            {"ladder": None, "discountPrice": 0.4},
            {"ladder": 10, "discountPrice": None},
        ]
    )

    product = Product.from_api(raw)

    assert [pb.quantity for pb in product.price_breaks] == [1]


def test_from_api_defaults_missing_optional_fields():
    product = Product.from_api({"productCode": "C1"})

    assert product.product_model == ""
    assert product.product_arrange == ""
    assert product.stock_number == 0
    assert product.product_images == []
    assert product.price_breaks == []
    assert product.moq is None


def test_detail_url_built_from_product_code():
    product = Product.from_api(_raw_product(productCode="C99999"))

    assert product.detail_url == "https://www.lcsc.com/product-detail/C99999.html"


def test_raw_keeps_full_payload():
    raw = _raw_product()
    product = Product.from_api(raw)

    assert product.raw == raw
