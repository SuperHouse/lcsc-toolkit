import pytest

from lcsc_toolkit.errors import LcscApiError
from lcsc_toolkit.orders.session import _extract_is_login


def test_extract_is_login_true():
    payload = {"code": 200, "result": {"isLogin": True, "customerCode": "X"}}

    assert _extract_is_login(payload) is True


def test_extract_is_login_false():
    payload = {"code": 200, "result": {"isLogin": False}}

    assert _extract_is_login(payload) is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"code": 500, "result": {"isLogin": True}},
        {"code": 200, "result": None},
        {"code": 200, "result": {}},
        {"code": 200},
        "not a dict",
        None,
    ],
)
def test_extract_is_login_raises_for_unexpected_shapes(payload):
    with pytest.raises(LcscApiError):
        _extract_is_login(payload)
