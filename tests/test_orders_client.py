import pytest

from lcsc_toolkit.errors import LcscApiError, SessionExpiredError
from lcsc_toolkit.orders.client import OrdersClient
from lcsc_toolkit.orders.session import LcscSession


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _client_returning(monkeypatch, payload, status_code=200):
    client = OrdersClient(LcscSession(cookies=[]), min_request_interval=0)
    monkeypatch.setattr(client._http, "get", lambda *args, **kwargs: FakeResponse(payload, status_code))
    return client


def test_get_returns_result_for_code_200(monkeypatch):
    client = _client_returning(monkeypatch, {"code": 200, "result": {"ok": True}})

    assert client._get("/wmsc/order/page") == {"ok": True}


def test_get_raises_session_expired_for_code_302(monkeypatch):
    # The exact shape observed from an expired session: HTTP 200, code 302, empty msg.
    payload = {"code": 302, "msg": ""}
    client = _client_returning(monkeypatch, payload)

    with pytest.raises(SessionExpiredError) as exc_info:
        client._get("/wmsc/order/page")

    assert exc_info.value.status_code == 200
    assert exc_info.value.payload == payload
    assert "session has expired" in str(exc_info.value)
    assert "/wmsc/order/page" in str(exc_info.value)


def test_session_expired_is_still_an_lcsc_api_error(monkeypatch):
    # Callers written before SessionExpiredError existed catch LcscApiError.
    client = _client_returning(monkeypatch, {"code": 302, "msg": ""})

    with pytest.raises(LcscApiError):
        client._get("/wmsc/order/page")


def test_list_orders_raises_session_expired(monkeypatch):
    client = _client_returning(monkeypatch, {"code": 302, "msg": ""})

    with pytest.raises(SessionExpiredError):
        client.list_orders()


def test_get_order_detail_raises_session_expired(monkeypatch):
    client = _client_returning(monkeypatch, {"code": 302, "msg": ""})

    with pytest.raises(SessionExpiredError):
        client.get_order_detail("some-uuid")


@pytest.mark.parametrize("payload", [{"code": 500, "msg": "server error"}, {"code": 401, "msg": ""}])
def test_get_raises_plain_api_error_for_other_codes(monkeypatch, payload):
    client = _client_returning(monkeypatch, payload)

    with pytest.raises(LcscApiError) as exc_info:
        client._get("/wmsc/order/page")

    assert not isinstance(exc_info.value, SessionExpiredError)


def test_get_raises_plain_api_error_for_http_error(monkeypatch):
    client = _client_returning(monkeypatch, {}, status_code=503)

    with pytest.raises(LcscApiError) as exc_info:
        client._get("/wmsc/order/page")

    assert not isinstance(exc_info.value, SessionExpiredError)
    assert exc_info.value.status_code == 503
