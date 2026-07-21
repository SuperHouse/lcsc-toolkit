"""Plain-`requests` client for LCSC's order-history endpoints.

Both endpoints here are undocumented - discovered by watching the network
traffic personalCenter/order/list makes while logged in - not part of any
published LCSC API. They may change or disappear without notice.

Despite living under an authenticated, logged-in area of the site, both
were confirmed to work when called directly with a saved session's cookies
and no live browser - see OrdersClient.__init__.
"""

import time

import requests

from lcsc_toolkit.errors import LcscApiError
from lcsc_toolkit.orders.types import OrderDetail, OrdersPage

BASE_URL = "https://wmsc.lcsc.com"

DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
}

# LCSC gets the most conservative pacing of any supplier this toolkit's
# sibling project talks to, since this is an unofficial client hitting a
# logged-in account area rather than a published API.
DEFAULT_MIN_REQUEST_INTERVAL = 3.0


class OrdersClient:
    """A client for LCSC's order-history endpoints, authenticated via a
    previously-captured `LcscSession`.

    Example:
        session = LcscSession.load("session.json")
        client = OrdersClient(session)
        page = client.list_orders()
        for order in page.orders:
            detail = client.get_order_detail(order.uuid)
            for line in detail.line_items:
                print(line.product_code, line.purchase_quantity)
    """

    def __init__(self, session, *, min_request_interval=DEFAULT_MIN_REQUEST_INTERVAL):
        self._http = requests.Session()
        self._http.cookies = session.to_requests_cookiejar()
        self._http.headers.update(DEFAULT_HEADERS)
        self._min_request_interval = min_request_interval
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        elapsed = time.monotonic() - self._last_request_time
        remaining = self._min_request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, path, params=None):
        self._respect_rate_limit()
        try:
            response = self._http.get(f"{BASE_URL}{path}", params=params, timeout=15)
        except requests.RequestException as exc:
            raise LcscApiError(f"Request to {path} failed: {exc}") from exc
        finally:
            self._last_request_time = time.monotonic()

        if response.status_code != 200:
            raise LcscApiError(
                f"{path} returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        payload = response.json()
        if payload.get("code") != 200:
            raise LcscApiError(
                f"{path} returned code={payload.get('code')}: {payload.get('msg')}",
                status_code=response.status_code,
                payload=payload,
            )

        return payload["result"]

    def list_orders(
        self,
        *,
        query_type="all",
        create_start_time="",
        create_end_time="",
        product_mpn="",
        keyword="",
        product_keyword="",
        web_order_status="",
        current_page=1,
        page_size=25,
        sort_type="timeDesc",
    ):
        """List orders. Mirrors the params personalCenter/order/list sends;
        all but `current_page`/`page_size` are optional filters LCSC's own
        search box uses and are untested here beyond being accepted."""
        params = {
            "queryType": query_type,
            "createStartTime": create_start_time,
            "createEndTime": create_end_time,
            "productMpn": product_mpn,
            "keyword": keyword,
            "productKeyword": product_keyword,
            "webOrderStatus": web_order_status,
            "currentPage": current_page,
            "pageSize": page_size,
            "sortType": sort_type,
        }
        result = self._get("/wmsc/order/page", params=params)
        return OrdersPage.from_api(result)

    def iter_orders(self, *, page_size=25, **kwargs):
        """Yield every OrderSummary across all pages, oldest filtering
        params passed through unchanged - see list_orders()."""
        current_page = 1
        while True:
            page = self.list_orders(current_page=current_page, page_size=page_size, **kwargs)
            yield from page.orders
            if current_page >= (page.total_page or 1):
                return
            current_page += 1

    def get_order_detail(self, order_uuid):
        """Fetch one order's full detail, including line items.

        `order_uuid` is the `uuid` field from an OrderSummary (list_orders),
        not the human-readable `order_code` - LCSC's detail endpoint takes
        a different identifier (`orderUuId`) than the order code shown in
        their UI.
        """
        result = self._get("/wmsc/order/detail", params={"orderUuId": order_uuid})
        return OrderDetail.from_api(result)
