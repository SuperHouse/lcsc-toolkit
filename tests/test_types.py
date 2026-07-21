from lcsc_toolkit.orders.types import OrderDetail, OrdersPage


def _raw_order_row(**overrides):
    row = {
        "uuid": "UUID1",
        "orderCode": "WM1234567890",
        "webOrderStatus": "Delivered",
        "paymentStatus": "paid",
        "orderAmount": 12.34,
        "currencyType": "USD",
        "createTime": "2026-01-01 00:00:00",
        "trackingCode": "TRACK123",
        "expressType": "DHL",
    }
    row.update(overrides)
    return row


def _raw_orders_page(rows):
    return {
        "currPage": 1,
        "pageRow": 25,
        "totalPage": 1,
        "totalRow": len(rows),
        "dataList": rows,
    }


def _raw_line_item(**overrides):
    item = {
        "productCode": "C12345",
        "productMpn": "ABC-123",
        "description": "Widget",
        "purchaseQuantity": 10,
        "unitPrice": 0.5,
        "realPrice": 0.45,
        "totalPrice": 5.0,
        "realTotalAmount": 4.5,
    }
    item.update(overrides)
    return item


def _raw_order_detail(line_items):
    return {
        "uuid": "UUID1",
        "orderCode": "WM1234567890",
        "webOrderStatus": "Delivered",
        "createTime": "2026-01-01 00:00:00",
        "trackingCode": "TRACK123",
        "expressType": "DHL",
        "orderProductVOList": line_items,
    }


def test_orders_page_from_api_parses_rows_and_pagination():
    page = OrdersPage.from_api(_raw_orders_page([_raw_order_row(), _raw_order_row(uuid="UUID2")]))

    assert page.total_row == 2
    assert [o.uuid for o in page.orders] == ["UUID1", "UUID2"]
    assert page.orders[0].order_code == "WM1234567890"
    assert page.orders[0].order_amount == 12.34


def test_orders_page_from_api_handles_empty_data_list():
    page = OrdersPage.from_api({"currPage": 1, "pageRow": 25, "totalPage": 0, "totalRow": 0, "dataList": None})

    assert page.orders == []


def test_order_detail_from_api_parses_line_items():
    detail = OrderDetail.from_api(_raw_order_detail([_raw_line_item(), _raw_line_item(productCode="C99999")]))

    assert detail.order_code == "WM1234567890"
    assert [li.product_code for li in detail.line_items] == ["C12345", "C99999"]
    assert detail.line_items[0].purchase_quantity == 10
    assert detail.line_items[0].real_price == 0.45


def test_order_detail_from_api_keeps_raw_payload():
    raw = _raw_order_detail([])
    detail = OrderDetail.from_api(raw)

    assert detail.raw == raw
