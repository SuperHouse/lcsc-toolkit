import json

from lcsc_toolkit.search.client import _extract_next_data_page_props


def _html_with_next_data(page_props):
    payload = json.dumps({"props": {"pageProps": page_props}})
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{payload}</script></body></html>'


def test_extract_next_data_page_props_parses_embedded_json():
    html = _html_with_next_data({"webData": {"productCode": "C1"}, "dataIsNull": False})

    page_props = _extract_next_data_page_props(html)

    assert page_props["webData"]["productCode"] == "C1"
    assert page_props["dataIsNull"] is False


def test_extract_next_data_page_props_missing_script_tag():
    html = "<html><body>no next data here</body></html>"

    assert _extract_next_data_page_props(html) == {}


def test_extract_next_data_page_props_unparseable_json():
    html = '<script id="__NEXT_DATA__">{not valid json</script>'

    assert _extract_next_data_page_props(html) == {}


def test_extract_next_data_page_props_missing_props_key():
    html = '<script id="__NEXT_DATA__">{"somethingElse": true}</script>'

    assert _extract_next_data_page_props(html) == {}
