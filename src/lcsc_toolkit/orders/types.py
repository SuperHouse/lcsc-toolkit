"""Typed views over LCSC's order API responses.

Each type only pulls out the fields that have actually been observed and
are useful; every LCSC field LCSC returned is still available on `.raw`,
since the full response shape is large, only partially explored, and liable
to gain/lose fields without notice - `.raw` means a consumer isn't blocked
on this library modelling a field before they can use it.
"""

from dataclasses import dataclass, field


@dataclass
class OrderSummary:
    """One row from GET /wmsc/order/page - see OrdersClient.list_orders()."""

    uuid: str
    order_code: str
    web_order_status: str
    payment_status: str
    order_amount: float
    currency_type: str
    create_time: str
    tracking_code: str
    express_type: str
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, data):
        return cls(
            uuid=data.get("uuid"),
            order_code=data.get("orderCode"),
            web_order_status=data.get("webOrderStatus"),
            payment_status=data.get("paymentStatus"),
            order_amount=data.get("orderAmount"),
            currency_type=data.get("currencyType"),
            create_time=data.get("createTime"),
            tracking_code=data.get("trackingCode"),
            express_type=data.get("expressType"),
            raw=data,
        )


@dataclass
class OrdersPage:
    """The result of GET /wmsc/order/page."""

    curr_page: int
    page_row: int
    total_page: int
    total_row: int
    orders: list
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, data):
        return cls(
            curr_page=data.get("currPage"),
            page_row=data.get("pageRow"),
            total_page=data.get("totalPage"),
            total_row=data.get("totalRow"),
            orders=[OrderSummary.from_api(row) for row in data.get("dataList") or []],
            raw=data,
        )


@dataclass
class OrderLineItem:
    """One entry from OrderDetail.line_items (LCSC's `orderProductVOList`)."""

    product_code: str
    product_mpn: str
    description: str
    purchase_quantity: int
    unit_price: float
    real_price: float
    total_price: float
    real_total_amount: float
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, data):
        return cls(
            product_code=data.get("productCode"),
            product_mpn=data.get("productMpn"),
            description=data.get("description"),
            purchase_quantity=data.get("purchaseQuantity"),
            unit_price=data.get("unitPrice"),
            real_price=data.get("realPrice"),
            total_price=data.get("totalPrice"),
            real_total_amount=data.get("realTotalAmount"),
            raw=data,
        )


@dataclass
class OrderDetail:
    """The result of GET /wmsc/order/detail - see OrdersClient.get_order_detail()."""

    uuid: str
    order_code: str
    web_order_status: str
    create_time: str
    tracking_code: str
    express_type: str
    line_items: list
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, data):
        return cls(
            uuid=data.get("uuid"),
            order_code=data.get("orderCode"),
            web_order_status=data.get("webOrderStatus"),
            create_time=data.get("createTime"),
            tracking_code=data.get("trackingCode"),
            express_type=data.get("expressType"),
            line_items=[
                OrderLineItem.from_api(row)
                for row in data.get("orderProductVOList") or []
            ],
            raw=data,
        )
