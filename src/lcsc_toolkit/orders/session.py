"""Capturing and reusing an authenticated LCSC session.

LCSC's order-history endpoints require being logged in to lcsc.com, and
there's no OAuth-style token/refresh flow to automate that (unlike this
project's DigiKey integration) - a human has to log in through a real
browser, including any CAPTCHA/2FA. `LcscSession.capture_interactively()`
does that once; the resulting cookies can then be reused with plain
`requests` (confirmed empirically - see the project README) for as long as
the session stays valid.
"""

import json

import requests

from lcsc_toolkit.errors import LcscApiError
from lcsc_toolkit.orders._http import BASE_URL, DEFAULT_HEADERS

DEFAULT_LOGIN_URL = "https://www.lcsc.com/login"
ORDER_LIST_URL = "https://www.lcsc.com/personalCenter/order/list"
LOGIN_CHECK_PATH = "/wmsc/login/user/info"


def _extract_is_login(payload):
    """Interpret the JSON body of a call to the login-check endpoint.

    Only the "definitely logged in" (True) and "definitely logged out"
    (False) cases are inferred directly from the one response shape this
    library has actually observed for a *valid* session -
    `{"code":200,"result":{"isLogin":bool,...}}` - trusting `isLogin`
    either way. Anything else raises LcscApiError rather than guessing,
    since what an actually-expired session's response looks like hasn't
    been confirmed yet (see the project README's Open Questions).
    """
    if not isinstance(payload, dict) or payload.get("code") != 200:
        raise LcscApiError(
            "Unexpected response checking session validity", payload=payload
        )
    result = payload.get("result")
    if not isinstance(result, dict) or "isLogin" not in result:
        raise LcscApiError(
            "Unexpected response shape checking session validity", payload=payload
        )
    return bool(result["isLogin"])


class LcscSession:
    """A saved/loaded set of LCSC login cookies."""

    def __init__(self, cookies):
        # Each cookie is a dict with at least name/value/domain, matching
        # the shape Playwright's `BrowserContext.storage_state()` uses -
        # that's the format this is built from and saved back to, so
        # capture/save/load round-trip without translation.
        self.cookies = cookies

    @classmethod
    def load(cls, path):
        with open(path) as f:
            storage_state = json.load(f)
        return cls(storage_state.get("cookies", []))

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"cookies": self.cookies}, f, indent=2)

    def to_requests_cookiejar(self):
        jar = requests.cookies.RequestsCookieJar()
        for cookie in self.cookies:
            jar.set(cookie["name"], cookie["value"], domain=cookie.get("domain", ""))
        return jar

    def check_valid(self, *, timeout=15):
        """Make one lightweight authenticated request to check whether
        this session is still logged in.

        Useful right after copying a session file to a different machine
        (e.g. captured interactively on a desktop, then copied to a
        headless server that can't run a browser at all) to confirm it
        actually carries over, or before trusting a saved session in an
        unattended/scheduled script.

        Returns True/False for a clearly-interpretable response. Raises
        LcscApiError for a genuine request failure, or a response that
        doesn't match the one shape this library has confirmed for a valid
        session - it deliberately does not guess at what an expired
        session's response looks like, since that hasn't been observed yet
        (see the project README's Open Questions). A raised LcscApiError
        here should be treated as "couldn't determine", not as "definitely
        logged out".
        """
        try:
            response = requests.get(
                f"{BASE_URL}{LOGIN_CHECK_PATH}",
                cookies=self.to_requests_cookiejar(),
                headers=DEFAULT_HEADERS,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise LcscApiError(f"Session check request failed: {exc}") from exc

        if response.status_code != 200:
            raise LcscApiError(
                f"Session check returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LcscApiError(
                f"Session check returned unparseable JSON: {exc}"
            ) from exc

        return _extract_is_login(payload)

    @classmethod
    def capture_interactively(cls, *, login_url=DEFAULT_LOGIN_URL):
        """Open a real, visible browser and wait for a human to log in.

        Requires Playwright: `pip install lcsc-toolkit[auth]` then
        `playwright install chromium`. Only needed for this one call - the
        rest of the library is plain `requests`.

        This never sees or stores your LCSC username/password. You do the
        login yourself in the browser window it opens, including any
        CAPTCHA/2FA.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is required for interactive login capture. "
                "Install it with: pip install lcsc-toolkit[auth] && "
                "playwright install chromium"
            ) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            page.goto(login_url)
            input(
                "A browser window has opened. Log in to LCSC manually "
                "(handle any CAPTCHA/2FA yourself), then press Enter here "
                "to continue... "
            )

            page.goto(ORDER_LIST_URL)
            page.wait_for_load_state("networkidle")
            if "login" in page.url.lower():
                print(
                    f"Warning: after navigating to the order list, ended up "
                    f"at {page.url}, which looks like a login page. Login "
                    "may not have completed."
                )

            storage_state = context.storage_state()
            browser.close()

        return cls(storage_state.get("cookies", []))
