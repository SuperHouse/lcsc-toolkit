class LcscToolkitError(Exception):
    """Base class for all errors raised by lcsc_toolkit."""


class LcscApiError(LcscToolkitError):
    """Raised when an LCSC API call fails or returns an unexpected shape.

    `status_code` is the HTTP status (may be None if the request itself
    failed before a response was received). `payload` is the parsed JSON
    body, when there was one - useful for inspecting LCSC's own `code`/`msg`
    fields when debugging.
    """

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class SessionExpiredError(LcscToolkitError):
    """Raised when the saved session no longer authenticates.

    LCSC has no automated re-login flow (no refresh token, unlike DigiKey's
    OAuth) - recovering from this means running the interactive login
    capture again.
    """
