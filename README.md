# lcsc-toolkit

An unofficial Python client for [LCSC](https://www.lcsc.com) that supports 
product search using the public site, and authenticated order history by 
logging in as a specific account.

WARNING: Everything here is reverse-engineered from LCSC's site, and may 
break without notice!

This library was created as part of the 
[Testomatic PCBA Register](https://github.com/superhouse/register) 
PCB testing and assembly management system, but doesn't depend on it.

## Disclaimer

- This is **not affiliated with, endorsed by, or supported by LCSC** in any
  way.
- Both modules work by replaying internal API calls LCSC's own website
  makes: `lcsc_toolkit.search` is the same public search box anyone gets
  without logging in, `lcsc_toolkit.orders` are the ones made while logged 
  in to *your* account. The order-history side is the one with real account
  risk: automated access to a logged-in account area may fall outside
  LCSC's terms of service. Think carefully before using it against your
  actual account. `search` isn't as risky because it's the same data
  everyone gets while browsing the site anonymously.
- There is no LCSC sandbox/staging environment. The endpoints this toolkit 
  module relies on could change or disappear at any time. For
  `orders`, repeated automated access could also trigger LCSC's bot
  detection and affect your account.
- Just in case I haven't been clear enough yet: USE AT YOUR OWN RISK!

## Install

```bash
pip install lcsc-toolkit          # core library (requests-only)
pip install lcsc-toolkit[auth]    # + Playwright, needed only for interactive login capture
playwright install chromium       # if you installed the [auth] extra
```

Install from PyPI using `pip install lcsc-toolkit`, or install from a local 
checkout with `pip install -e .`

## Order history

LCSC has no OAuth-style API key or refresh-token flow for this. You log in
to lcsc.com like a normal user, including any CAPTCHA/2FA, and the library
reuses the resulting session cookies. There's no way to automate the login
itself, and this library doesn't try to.

```python
from lcsc_toolkit.orders import LcscSession

# One-time, interactive: opens a real browser window and waits for you
# to log in by hand.
session = LcscSession.capture_interactively()
session.save("session.json")
```

Once captured, the session cookies work with plain `requests`. No browser is
needed for actual API calls.

```python
from lcsc_toolkit.orders import LcscSession, OrdersClient

session = LcscSession.load("session.json")
client = OrdersClient(session)

page = client.list_orders()
for order in page.orders:
    print(order.order_code, order.web_order_status, order.order_amount)

detail = client.get_order_detail(page.orders[0].uuid)
for line in detail.line_items:
    print(line.product_code, line.purchase_quantity, line.real_price)
```

See `examples/capture_session.py` and `examples/list_recent_orders.py` for
runnable versions of the above.

You can start by running the `capture_session.py` example which will 
attempt to launch a browser on your computer for you to log in to LCSC 
and then write the session cookie to disk, then run `list_recent_orders.py` 
to verify that it successfully connects to LCSC using the saved cookie.

Check whether a session is actually still logged in with `check_valid()`
(or `OrdersClient.check_session()`, an identical passthrough) - a single
lightweight authenticated request, useful right after loading a session
you didn't just capture yourself, before trusting it in a script:

```python
if not session.check_valid():
    raise SystemExit("Session expired - run capture_session.py again")
```

There's no automated way to detect a session has expired ahead
of time. `OrdersClient` calls raise `lcsc_toolkit.errors.LcscApiError` if
something goes wrong, which is your cue to check the session and probably
re-capture it. How long a session actually stays valid in the first place
hasn't been worked out yet and may be unpredictable, depending on what 
LCSC do with their servers: reboots, garbage cleanup, etc.

## Running on a headless server

Interactive login (`capture_interactively()`) needs a real, visible browser
window, which a headless server doesn't have. The fix is to split
capture and use across two machines:

1. Run `examples/capture_session.py` on any machine with a display (your
   desktop) to log in and produce a session file.
2. Copy that file to the server.
3. On the server, `LcscSession.load(...)` + `OrdersClient` - this only
   needs `requests`, not Playwright, so the server never needs the `[auth]`
   extra or a browser at all.

This works because the session is just cookies. There's nothing browser-
or machine-specific baked into them. **Confirmed working**: a session
captured on a desktop, copied to a separate remote machine on a different
network, authenticated successfully there. LCSC does not appear to tie
the session to the originating IP address. Still, run `check_valid()`
right after copying a session file over, before wiring anything up to run
unattended, as confirmation for your own setup.

## Product search

No login or session required. `SearchClient` is simple page loads.

```python
from lcsc_toolkit.search import SearchClient

client = SearchClient()
product = client.search("C17179461")  # SKU or manufacturer part number

if product:
    print(product.product_model, product.stock_number, product.detail_url)
    for pb in product.price_breaks:
        print(pb.quantity, pb.price, pb.currency)
else:
    print("No match")
```

`search()` returns `None` for no match, a `Product` otherwise. Errors
(request failures, unexpected response shapes) raise
`lcsc_toolkit.errors.LcscApiError`, same as `orders`.

## How LCSC's order API works

Discovered by watching personalCenter/order/list's own network traffic
while logged in (see `examples/explore_network.py`), not from any published
LCSC documentation so YMMV.

- **List**: `GET https://wmsc.lcsc.com/wmsc/order/page`, query params
  `queryType`, `createStartTime`, `createEndTime`, `productMpn`, `keyword`,
  `productKeyword`, `webOrderStatus`, `currentPage`, `pageSize`, `sortType`.
  Response: `{"code":200,"result":{"currPage","pageRow","totalPage",
  "totalRow","dataList":[{"uuid","orderCode","webOrderStatus",
  "paymentStatus","orderAmount","currencyType","createTime","trackingCode",
  "expressType",...}]}}`. `orderCode` (eg: `WM2607080353`) is the
  human-readable order number; `uuid` is what the detail endpoint needs.
- **Detail**: `GET https://wmsc.lcsc.com/wmsc/order/detail?orderUuId=<uuid>`
  - note the param name (`orderUuId`) doesn't match the list row's field
  name (`uuid`) or casing. Result includes order-level fields plus
  **`orderProductVOList`**, the line items: `productCode` (LCSC's own SKU,
  eg: `C17179461`), `productMpn`, `description`, `purchaseQuantity`,
  `unitPrice` (pre-discount list price), `realPrice` (the actual per-unit
  price paid), `totalPrice`/`realTotalAmount`.
- **Session cookies work via plain `requests`, no browser needed
  post-login**. Confirmed by replaying both endpoints above with just the
  saved cookies and getting the same data back as the browser did.
- **Sessions are portable across machines/networks**. A session captured
  on one machine, copied to a separate remote machine, authenticated
  successfully from there. See Running on a headless server, above.

## How LCSC's search API works

- **Search**: `POST https://wmsc.lcsc.com/ftps/wm/search/v3/global`, JSON
  body `{keyword, secondKeyword, brandIdList, catalogIdList, isStock,
  isAsianBrand, isDeals, isEnvironment}`. Response `result.scene` is either
  `FULL_MATCH` (product is `result.exactMatchResult[0]`) or
  `REDIRECT_PRODUCT_DETAIL` (search didn't resolve to one exact product:
  see below).
- **Product detail fallback**: on `REDIRECT_PRODUCT_DETAIL`,
  `result.tipProductDetailUrlVO.productCode` identifies a product page at
  `https://www.lcsc.com/product-detail/<productCode>.html`, but that's an
  HTML page, not a JSON API. The data is embedded in a
  `<script id="__NEXT_DATA__">` tag as JSON (`props.pageProps.webData`).
  `SearchClient` fetches that page and regex-extracts the blob rather than
  parsing HTML properly, since the actual product data is just JSON
  sitting inside a `<script>` tag. Falls back to the (much sparser) `tip`
  object itself if that data isn't there or `dataIsNull` is true.
- **Pricing**: `productPriceList` entries (`{ladder, discountPrice}`) map
  to price-break quantity/price pairs. Like orders, LCSC's search API only
  ever returns a `"$"` symbol, not an ISO currency code, so currency is
  assumed `USD`.
- No authentication of any kind: confirmed by this being the same data
  visiting lcsc.com and searching anonymously returns.

## Open questions

Not yet answered, and worth knowing before relying on this for anything
unattended (e.g. a scheduled sync). All of these are specific to `orders`:

- **How long does a captured session stay valid?** If it's
  short-lived, a scheduled/unattended sync isn't practical without solving
  re-authentication some other way. There's no refresh-token equivalent
  to automate that, unlike an OAuth-based API.
- **What does an expired-session response look like?** (HTTP
  status, or a `code`/`msg` in the body?) Not yet observed against a real
  expired session: `check_valid()` (see above) only trusts the one shape
  confirmed for a *valid* session and raises for anything else, rather than
  assuming what "expired" looks like.
- Whether there's a lighter-weight way to keep a session alive (e.g.
  periodic no-op requests) versus needing a fresh interactive login each
  time it lapses.

## Project layout

```
src/lcsc_toolkit/
├── errors.py             # LcscToolkitError, LcscApiError, SessionExpiredError
├── orders/
│   ├── session.py        # LcscSession: capture/save/load a login session, check_valid()
│   ├── client.py         # OrdersClient: list_orders(), iter_orders(), get_order_detail(), check_session()
│   ├── types.py          # OrderSummary, OrdersPage, OrderLineItem, OrderDetail (line items and orders both expose a stable `uuid`; OrderSummary/OrderDetail have `detail_url`)
│   └── _http.py          # shared BASE_URL/headers for the wmsc.lcsc.com API
└── search/
    ├── client.py         # SearchClient: search() (no login required)
    └── types.py          # Product, PriceBreak
examples/
├── capture_session.py    # interactive login capture (needs the [auth] extra)
├── list_recent_orders.py # minimal usage example of the confirmed order-history API
└── explore_network.py    # diagnostic tool for discovering further order-related endpoints
tests/
```

## License

MIT - see [LICENSE](LICENSE).
