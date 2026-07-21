import json

from lcsc_toolkit.orders import LcscSession


def _cookie(name="lcsc_token", value="abc123", domain=".lcsc.com"):
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": "/",
        "expires": -1,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax",
    }


def test_save_and_load_round_trip(tmp_path):
    session = LcscSession([_cookie()])
    path = tmp_path / "storage_state.json"

    session.save(path)
    reloaded = LcscSession.load(path)

    assert reloaded.cookies == session.cookies


def test_save_writes_storage_state_shape(tmp_path):
    session = LcscSession([_cookie()])
    path = tmp_path / "storage_state.json"

    session.save(path)

    with open(path) as f:
        data = json.load(f)
    assert data == {"cookies": [_cookie()]}


def test_load_ignores_extra_storage_state_keys(tmp_path):
    # Playwright's real storage_state() output also has an "origins" key
    # (localStorage per-origin) - loading should tolerate that even though
    # this library only uses cookies today.
    path = tmp_path / "storage_state.json"
    path.write_text(json.dumps({"cookies": [_cookie()], "origins": []}))

    session = LcscSession.load(path)

    assert session.cookies == [_cookie()]


def test_to_requests_cookiejar_carries_name_and_value():
    session = LcscSession([_cookie(name="foo", value="bar")])

    jar = session.to_requests_cookiejar()

    assert jar.get("foo") == "bar"
