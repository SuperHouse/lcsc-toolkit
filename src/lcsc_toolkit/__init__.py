"""lcsc-toolkit: an unofficial Python client for LCSC.com.

Currently covers order history (`lcsc_toolkit.orders`, needs a logged-in
session) and product search (`lcsc_toolkit.search`, no login required).
LCSC does not publish a public API for any of this - everything here is
reverse-engineered from what LCSC's own website calls internally, and may
break without notice.
"""

__version__ = "0.1.0"
