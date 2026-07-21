#!/usr/bin/env python3
"""
Minimal usage example for the confirmed, working part of the library:
list your recent LCSC orders and print their line items, using only a
saved session and plain `requests` - no browser involved here.

Usage:
    python examples/capture_session.py   # first, to create a session
    python examples/list_recent_orders.py

Environment variables:
    LCSC_SESSION_FILE: session file written by capture_session.py
                        (default: ./.lcsc_session/storage_state.json)
    LCSC_ORDER_COUNT: how many recent orders to show details for
                       (default: 3)
"""

import os
import sys
from pathlib import Path

from lcsc_toolkit.errors import LcscApiError
from lcsc_toolkit.orders import LcscSession, OrdersClient

DEFAULT_SESSION_FILE = "./.lcsc_session/storage_state.json"


def main():
    session_file = Path(os.environ.get("LCSC_SESSION_FILE", DEFAULT_SESSION_FILE))
    order_count = int(os.environ.get("LCSC_ORDER_COUNT", "3"))

    if not session_file.exists():
        print(f"Error: session file not found at {session_file}")
        print("Run examples/capture_session.py first.")
        sys.exit(1)

    session = LcscSession.load(session_file)
    client = OrdersClient(session)

    try:
        page = client.list_orders(page_size=order_count)
    except LcscApiError as exc:
        print(f"Failed to list orders: {exc}")
        print("The session may have expired - try running "
              "examples/capture_session.py again.")
        sys.exit(1)

    print(f"{page.total_row} order(s) total, showing the {len(page.orders)} most recent:")
    print()

    for order in page.orders:
        print(f"{order.order_code}  {order.web_order_status:12}  "
              f"{order.currency_type} {order.order_amount}  {order.create_time}")
        detail = client.get_order_detail(order.uuid)
        for line in detail.line_items:
            print(f"    {line.product_code:12} x{line.purchase_quantity:<6} "
                  f"{line.description}")
        print()


if __name__ == "__main__":
    main()
