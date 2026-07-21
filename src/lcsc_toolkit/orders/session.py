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

DEFAULT_LOGIN_URL = "https://www.lcsc.com/login"
ORDER_LIST_URL = "https://www.lcsc.com/personalCenter/order/list"


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
