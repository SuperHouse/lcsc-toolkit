"""Plain-`requests` client for LCSC's public product search.

Unlike `lcsc_toolkit.orders`, this needs no LcscSession/login at all - it's
the same public catalog search LCSC's own search box uses, reverse-
engineered from that (undocumented, may change without notice).
"""

import json
import re
import time

import requests

from lcsc_toolkit.errors import LcscApiError
from lcsc_toolkit.search.types import Product

SEARCH_BASE_URL = "https://wmsc.lcsc.com"
PRODUCT_DETAIL_BASE_URL = "https://www.lcsc.com"

DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.lcsc.com",
    "referer": "https://www.lcsc.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Same conservative default as OrdersClient - LCSC gets the most cautious
# pacing of any supplier this toolkit's sibling project talks to, since
# every endpoint here is unofficial.
DEFAULT_MIN_REQUEST_INTERVAL = 3.0

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def _extract_next_data_page_props(html):
    """Pure: pull `props.pageProps` out of an LCSC product-detail page's
    embedded __NEXT_DATA__ JSON blob. Returns {} if it isn't present or
    isn't parseable, rather than raising - a missing/changed blob is a
    "no match" signal to the caller, not a hard failure."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except (ValueError, TypeError):
        return {}
    return data.get("props", {}).get("pageProps", {}) or {}


class SearchClient:
    """A client for LCSC's public product search - no login required.

    Example:
        client = SearchClient()
        product = client.search("C17179461")
        if product:
            print(product.product_model, product.stock_number)
            for pb in product.price_breaks:
                print(pb.quantity, pb.price)
    """

    def __init__(self, *, min_request_interval=DEFAULT_MIN_REQUEST_INTERVAL):
        self._http = requests.Session()
        self._http.headers.update(DEFAULT_HEADERS)
        self._min_request_interval = min_request_interval
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        elapsed = time.monotonic() - self._last_request_time
        remaining = self._min_request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def search(
        self,
        keyword,
        *,
        second_keyword="",
        brand_ids=None,
        catalog_ids=None,
        in_stock_only=False,
        asian_brand_only=False,
        deals_only=False,
        environment_only=False,
    ):
        """Look up a product by SKU or keyword.

        `keyword` is usually a manufacturer part number or an LCSC product
        code. Returns a Product, or None if nothing matched. The other
        parameters mirror filters LCSC's own search box exposes; they're
        accepted and passed through but only `keyword` has actually been
        exercised here.
        """
        body = {
            "keyword": keyword,
            "secondKeyword": second_keyword,
            "brandIdList": brand_ids or [],
            "catalogIdList": catalog_ids or [],
            "isStock": in_stock_only,
            "isAsianBrand": asian_brand_only,
            "isDeals": deals_only,
            "isEnvironment": environment_only,
        }

        envelope = self._post_json(f"{SEARCH_BASE_URL}/ftps/wm/search/v3/global", body)
        result = envelope.get("result") or {}
        scene = result.get("scene")

        raw_product = None
        if scene == "FULL_MATCH" and result.get("exactMatchResult"):
            raw_product = result["exactMatchResult"][0]
        elif scene == "REDIRECT_PRODUCT_DETAIL" and result.get("tipProductDetailUrlVO"):
            tip = result["tipProductDetailUrlVO"]
            page_props = self._fetch_product_detail_page_props(tip["productCode"])
            if page_props.get("webData") and not page_props.get("dataIsNull"):
                raw_product = page_props["webData"]
            else:
                raw_product = tip

        if raw_product is None:
            return None
        return Product.from_api(raw_product)

    def _post_json(self, url, body):
        self._respect_rate_limit()
        try:
            response = self._http.post(url, json=body, timeout=15)
        except requests.RequestException as exc:
            raise LcscApiError(f"Request to {url} failed: {exc}") from exc
        finally:
            self._last_request_time = time.monotonic()

        if response.status_code != 200:
            raise LcscApiError(
                f"{url} returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        envelope = response.json()
        if envelope.get("code") != 200:
            raise LcscApiError(
                f"{url} returned code={envelope.get('code')}: {envelope.get('msg')}",
                status_code=response.status_code,
                payload=envelope,
            )
        return envelope

    def _fetch_product_detail_page_props(self, product_code):
        self._respect_rate_limit()
        url = f"{PRODUCT_DETAIL_BASE_URL}/product-detail/{product_code}.html"
        try:
            response = self._http.get(url, headers={"accept": "text/html"}, timeout=15)
        except requests.RequestException as exc:
            raise LcscApiError(f"Request to {url} failed: {exc}") from exc
        finally:
            self._last_request_time = time.monotonic()

        if response.status_code != 200:
            raise LcscApiError(
                f"{url} returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        return _extract_next_data_page_props(response.text)
