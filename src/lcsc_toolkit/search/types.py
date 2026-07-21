"""Typed views over LCSC's product search API responses.

Like `lcsc_toolkit.orders.types`, only fields that have actually been
observed and are useful are pulled out; `.raw` carries the full response so
a consumer isn't blocked on this library modelling a field before they can
use it.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriceBreak:
    """One quantity-based pricing tier (e.g. qty 1 @ $0.50, qty 10 @ $0.45)."""

    quantity: int
    price: float
    currency: str = "USD"


@dataclass
class Product:
    """A single product match from SearchClient.search()."""

    product_code: str
    product_model: str
    product_arrange: str
    stock_number: int
    product_intro_en: str
    product_images: list
    price_breaks: list
    moq: Optional[int]
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def detail_url(self):
        return f"https://www.lcsc.com/product-detail/{self.product_code}.html"

    @classmethod
    def from_api(cls, data):
        price_breaks = []
        for item in data.get("productPriceList") or []:
            quantity = item.get("ladder")
            price = item.get("discountPrice")
            if quantity is not None and price is not None:
                # LCSC's API only ever returns a "$" symbol, not an ISO
                # code, so currency is assumed USD - same convention this
                # toolkit's sibling project uses for every other supplier.
                price_breaks.append(
                    PriceBreak(quantity=quantity, price=price, currency="USD")
                )

        return cls(
            product_code=data.get("productCode", ""),
            product_model=data.get("productModel") or "",
            product_arrange=data.get("productArrange") or "",
            stock_number=data.get("stockNumber") or 0,
            product_intro_en=data.get("productIntroEn") or "",
            product_images=data.get("productImages") or [],
            price_breaks=price_breaks,
            moq=data.get("minBuyNumber"),
            raw=data,
        )
