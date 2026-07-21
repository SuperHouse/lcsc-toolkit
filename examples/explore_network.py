#!/usr/bin/env python3
"""
Diagnostic tool for discovering more of LCSC's internal JSON API beyond
what this library already covers (order list/detail). Loads a saved
session, opens the order list page, and records every XHR/fetch call made
while you click around manually - useful if this toolkit grows to cover
more of personalCenter (refunds, invoices, etc.) later.

Order rows in the list are not plain <a href> links (LCSC's order list is a
client-side app, not server-rendered navigation), so this script does not
try to guess how to click into anything itself - it opens a visible browser
and asks you to click around while it keeps recording in the background.

This is a diagnostic/exploration tool, not part of the library's public
API - see list_recent_orders.py for a normal usage example.

Usage:
    python examples/capture_session.py   # first, to create a session
    python examples/explore_network.py

Environment variables:
    LCSC_SESSION_FILE: session file written by capture_session.py
                        (default: ./.lcsc_session/storage_state.json)
    LCSC_REPORT_DIR: where to write the findings report and screenshots
                      (default: ./.lcsc_session/reports)
    LCSC_MAX_PAGES_TO_INSPECT: how many pages you'll be asked to click into
                                (default: 3)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright is required. Install it with:")
    print("    pip install lcsc-toolkit[auth]")
    print("    playwright install chromium")
    sys.exit(1)

import requests

from lcsc_toolkit.orders import LcscSession

DEFAULT_SESSION_FILE = "./.lcsc_session/storage_state.json"
DEFAULT_REPORT_DIR = "./.lcsc_session/reports"
ORDER_LIST_URL = "https://www.lcsc.com/personalCenter/order/list"
BODY_SNIPPET_LIMIT = 2000
REPLAY_DELAY_SECONDS = 1.0
MAX_ENDPOINTS_TO_REPLAY = 8


def get_config():
    return {
        "session_file": Path(os.environ.get("LCSC_SESSION_FILE", DEFAULT_SESSION_FILE)),
        "report_dir": Path(os.environ.get("LCSC_REPORT_DIR", DEFAULT_REPORT_DIR)),
        "max_pages": int(os.environ.get("LCSC_MAX_PAGES_TO_INSPECT", "3")),
    }


def looks_like_login_page(url):
    return "login" in url.lower()


class ApiCallRecorder:
    """Collects XHR/fetch calls seen on a page, deduped by (method, url)."""

    def __init__(self):
        self.calls = []
        self._seen = set()

    def attach(self, page):
        page.on("response", self._on_response)

    def _on_response(self, response):
        request = response.request
        if request.resource_type not in ("xhr", "fetch"):
            return
        key = (request.method, response.url)
        if key in self._seen:
            return
        self._seen.add(key)

        content_type = response.headers.get("content-type", "")
        body_snippet = ""
        if "json" in content_type or "text" in content_type:
            try:
                body_snippet = response.text()[:BODY_SNIPPET_LIMIT]
            except Exception as exc:  # response body may no longer be available
                body_snippet = f"<unreadable: {exc}>"

        self.calls.append(
            {
                "method": request.method,
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
                "body_snippet": body_snippet,
            }
        )


def replay_with_requests(session, api_calls):
    """Try replaying discovered GET JSON endpoints with plain requests,
    using the saved session's cookies but no live browser."""
    jar = session.to_requests_cookiejar()

    headers = {
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "accept": "application/json, text/plain, */*",
    }

    get_json_calls = [
        c for c in api_calls if c["method"] == "GET" and "json" in c["content_type"]
    ]
    get_json_calls.sort(key=lambda c: 0 if "order" in c["url"].lower() else 1)

    results = []
    for call in get_json_calls[:MAX_ENDPOINTS_TO_REPLAY]:
        time.sleep(REPLAY_DELAY_SECONDS)
        try:
            resp = requests.get(call["url"], cookies=jar, headers=headers, timeout=15)
            results.append(
                {
                    "url": call["url"],
                    "status": resp.status_code,
                    "content_type": resp.headers.get("content-type", ""),
                    "body_snippet": resp.text[:BODY_SNIPPET_LIMIT],
                }
            )
        except requests.RequestException as exc:
            results.append({"url": call["url"], "error": str(exc)})

    return results


def main():
    config = get_config()

    if not config["session_file"].exists():
        print(f"Error: session file not found at {config['session_file']}")
        print("Run examples/capture_session.py first.")
        sys.exit(1)

    config["report_dir"].mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    findings = {
        "captured_at": timestamp,
        "order_list_url": ORDER_LIST_URL,
        "session_valid": None,
        "final_url_after_nav": None,
        "api_calls": [],
        "pages_visited": [],
        "requests_replay": [],
        "screenshots": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(config["session_file"]))
        page = context.new_page()

        recorder = ApiCallRecorder()
        recorder.attach(page)

        print(f"Navigating to {ORDER_LIST_URL} ...")
        page.goto(ORDER_LIST_URL)
        page.wait_for_load_state("networkidle")

        findings["final_url_after_nav"] = page.url
        findings["session_valid"] = not looks_like_login_page(page.url)

        if not findings["session_valid"]:
            print()
            print(f"Session looks expired/invalid - ended up at {page.url}")
            print("Re-run examples/capture_session.py to capture a fresh session.")
        else:
            print("Session looks valid - order list page loaded.")

            list_screenshot = config["report_dir"] / f"{timestamp}_start.png"
            page.screenshot(path=str(list_screenshot))
            findings["screenshots"].append(str(list_screenshot))

            print()
            print(f"In the browser window, click around up to {config['max_pages']} "
                  "times (e.g. into orders, refunds, invoices) - the script keeps "
                  "recording network calls in the background while you do.")
            print("After each page finishes loading, come back here and press "
                  "Enter. Type 'done' instead to finish early.")

            for i in range(1, config["max_pages"] + 1):
                response = input(
                    f"Press Enter once page #{i} has loaded (or type 'done'): "
                )
                if response.strip().lower() == "done":
                    break
                page.wait_for_load_state("networkidle")
                findings["pages_visited"].append(page.url)
                shot = config["report_dir"] / f"{timestamp}_page_{i}.png"
                page.screenshot(path=str(shot))
                findings["screenshots"].append(str(shot))
                print(f"  Captured {page.url}")

        findings["api_calls"] = recorder.calls
        browser.close()

    if findings["session_valid"]:
        json_call_count = sum(
            1 for c in findings["api_calls"] if "json" in c["content_type"]
        )
        print()
        print(f"Captured {len(findings['api_calls'])} XHR/fetch call(s), "
              f"{json_call_count} with a JSON content-type.")

        if json_call_count:
            print("Replaying discovered GET JSON endpoints with plain requests "
                  "(no browser) to check whether the session cookie alone is enough ...")
            session = LcscSession.load(config["session_file"])
            findings["requests_replay"] = replay_with_requests(
                session, findings["api_calls"]
            )

    report_path = config["report_dir"] / f"{timestamp}_findings.json"
    with open(report_path, "w") as f:
        json.dump(findings, f, indent=2)

    print()
    print(f"Findings written to {report_path}")
    print(f"Screenshots written to {config['report_dir']}")


if __name__ == "__main__":
    main()
