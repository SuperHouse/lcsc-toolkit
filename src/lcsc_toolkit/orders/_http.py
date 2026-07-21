"""Shared HTTP constants for LCSC's internal wmsc.lcsc.com API.

Private to the `orders` package - both client.py and session.py talk to the
same host with the same headers, so it's defined once here rather than
duplicated.
"""

BASE_URL = "https://wmsc.lcsc.com"

DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
}
