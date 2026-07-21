#!/usr/bin/env python3
"""
Capture an authenticated LCSC session and save it for reuse by
explore_orders.py or your own code (via lcsc_toolkit.orders.LcscSession).

This does NOT automate login - it opens a real, visible browser window and
waits for you to log in by hand (including any CAPTCHA/2FA). It never sees
or stores your LCSC username/password.

Usage:
    pip install lcsc-toolkit[auth]
    playwright install chromium
    python examples/capture_session.py

Environment variables:
    LCSC_SESSION_FILE: where to save the captured session
                        (default: ./.lcsc_session/storage_state.json)
"""

import os
from pathlib import Path

from lcsc_toolkit.orders import LcscSession

DEFAULT_SESSION_FILE = "./.lcsc_session/storage_state.json"


def main():
    session_file = Path(os.environ.get("LCSC_SESSION_FILE", DEFAULT_SESSION_FILE))
    session_file.parent.mkdir(parents=True, exist_ok=True)

    session = LcscSession.capture_interactively()
    session.save(session_file)

    print(f"Session saved to {session_file}")
    print("Keep this file private - it is a live, replayable login session "
          "for your LCSC account. Do not commit it.")


if __name__ == "__main__":
    main()
