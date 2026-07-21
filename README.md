# lcsc-toolkit

An unofficial Python client for [LCSC](https://www.lcsc.com), with authenticated
order history. LCSC does not publish a public API for this. Everything
here is reverse-engineered from what LCSC's own website calls internally,
and may break without notice.

**Status: alpha.** Order history (list + detail) is implemented and has
been confirmed to work. Nothing else yet.

## Disclaimer

- This is **not affiliated with, endorsed by, or supported by LCSC** in any
  way.
- It works by replaying the same internal API calls LCSC's own website
  makes while you're logged in. Automated access to a logged-in account
  area may fall outside LCSC's terms of service. You need to think carefully
  before using this with your actual LCSC account!
- There is no LCSC sandbox/staging environment. The endpoints this relies
  on could change shape or disappear at any time, and repeated automated
  access could trigger LCSC's bot detection and affect your account, not
  just your script.
- Just in case it wasn't clear: USE AT YOUR OWN RISK!

## Install

```bash
pip install lcsc-toolkit          # core library (requests-only)
pip install lcsc-toolkit[auth]    # + Playwright, needed only for interactive login capture
playwright install chromium       # if you installed the [auth] extra
```

Not on PyPI yet. For now, install from a local checkout with `pip install -e .`

## How authentication works

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

Check whether a session is actually still logged in with `check_valid()`
(or `OrdersClient.check_session()`, an identical passthrough) - a single
lightweight authenticated request, useful right after loading a session
you didn't just capture yourself, before trusting it in a script:

```python
if not session.check_valid():
    raise SystemExit("Session expired - run capture_session.py again")
```

Beyond that, there's no automated way to detect a session has expired ahead
of time. `OrdersClient` calls raise `lcsc_toolkit.errors.LcscApiError` if
something goes wrong, which is your cue to check the session and probably
re-capture it. How long a session actually stays valid in the first place
hasn't been characterised yet.

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

This works because the session is just cookies - there's nothing browser-
or machine-specific baked into them. **Confirmed working**: a session
captured on a desktop, copied to a separate remote machine on a different
network, authenticated successfully there - so LCSC does not appear to tie
the session to the originating IP address. Still, run `check_valid()`
right after copying a session file over, before wiring anything up to run
unattended, as routine confirmation for your own setup - one confirmed
pair of machines isn't a guarantee for every network/hosting environment.

## Findings: how LCSC's order API works

Discovered by watching personalCenter/order/list's own network traffic
while logged in (see `examples/explore_network.py`), not from any published
LCSC documentation.

- **List**: `GET https://wmsc.lcsc.com/wmsc/order/page`, query params
  `queryType`, `createStartTime`, `createEndTime`, `productMpn`, `keyword`,
  `productKeyword`, `webOrderStatus`, `currentPage`, `pageSize`, `sortType`.
  Response: `{"code":200,"result":{"currPage","pageRow","totalPage",
  "totalRow","dataList":[{"uuid","orderCode","webOrderStatus",
  "paymentStatus","orderAmount","currencyType","createTime","trackingCode",
  "expressType",...}]}}`. `orderCode` (e.g. `WM2607080353`) is the
  human-readable order number; `uuid` is what the detail endpoint needs.
- **Detail**: `GET https://wmsc.lcsc.com/wmsc/order/detail?orderUuId=<uuid>`
  - note the param name (`orderUuId`) doesn't match the list row's field
  name (`uuid`) or casing. Result includes order-level fields plus
  **`orderProductVOList`**, the line items: `productCode` (LCSC's own SKU,
  e.g. `C17179461`), `productMpn`, `description`, `purchaseQuantity`,
  `unitPrice` (pre-discount list price), `realPrice` (the actual per-unit
  price paid), `totalPrice`/`realTotalAmount`.
- **Session cookies work via plain `requests`, no browser needed
  post-login** - confirmed by replaying both endpoints above with just the
  saved cookies and getting the same data back as the browser did.
- **Sessions are portable across machines/networks** - a session captured
  on one machine, copied to a separate remote machine, authenticated
  successfully from there. See Running on a headless server, above.

## Open questions

Not yet answered, and worth knowing before relying on this for anything
unattended (e.g. a scheduled sync):

- **How long does a captured session actually stay valid?** If it's
  short-lived, a scheduled/unattended sync isn't practical without solving
  re-authentication some other way. There's no refresh-token equivalent
  to automate that, unlike an OAuth-based API.
- **What does an expired-session response actually look like?** (HTTP
  status, or a `code`/`msg` in the body?) Not yet observed against a real
  expired session - `check_valid()` (see above) only trusts the one shape
  confirmed for a *valid* session and raises for anything else, rather than
  assuming what "expired" looks like.
- Whether there's a lighter-weight way to keep a session alive (e.g.
  periodic no-op requests) versus needing a fresh interactive login each
  time it lapses.

## Project layout

```
src/lcsc_toolkit/
├── errors.py           # LcscToolkitError, LcscApiError, SessionExpiredError
└── orders/
    ├── session.py       # LcscSession: capture/save/load a login session, check_valid()
    ├── client.py        # OrdersClient: list_orders(), iter_orders(), get_order_detail(), check_session()
    ├── types.py         # OrderSummary, OrdersPage, OrderLineItem, OrderDetail
    └── _http.py         # shared BASE_URL/headers for the wmsc.lcsc.com API
examples/
├── capture_session.py   # interactive login capture (needs the [auth] extra)
├── list_recent_orders.py  # minimal usage example of the confirmed API
└── explore_network.py   # diagnostic tool for discovering further endpoints
tests/
```

## License

MIT - see [LICENSE](LICENSE).
