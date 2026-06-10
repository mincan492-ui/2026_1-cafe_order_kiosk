from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from cafe_order_kiosk.models import MenuItem, Order, OrderItem, OrderStatus, Payment
from cafe_order_kiosk.utils import utc_now

DEFAULT_MENU: tuple[MenuItem, ...] = (
    MenuItem(id=1, name="Americano", price=3500, category="coffee"),
    MenuItem(id=2, name="Latte", price=4000, category="coffee"),
    MenuItem(id=3, name="Cappuccino", price=4200, category="coffee"),
    MenuItem(id=4, name="Cold Brew", price=4500, category="coffee"),
    MenuItem(id=5, name="Matcha Latte", price=4800, category="tea"),
    MenuItem(id=6, name="Chamomile Tea", price=3800, category="tea"),
    MenuItem(id=7, name="Lemonade", price=4200, category="juice"),
    MenuItem(id=8, name="Butter Croissant", price=3500, category="bakery"),
    MenuItem(id=9, name="Blueberry Muffin", price=3200, category="bakery"),
    MenuItem(id=10, name="Cheesecake", price=5200, category="dessert"),
)
RANDOM_DISCOUNT_RATES: tuple[int, ...] = (5, 10, 15, 20)
#할인율 경우의 수
#랜덤 할인 메뉴의 정보를 담는 객체
@dataclass(frozen=True)
class RandomDiscountMenuResult:
    menu_item: MenuItem
    discount_rate: int
    original_price: int
    discounted_price: int

class KioskStore:
    def __init__(self, menu_items: Iterable[MenuItem] | None = None ) -> None:
        self._menu: dict[int, MenuItem] = {item.id: item for item in (menu_items or [])}
        self._orders: dict[int, Order] = {}
        self._next_order_id = 1

    @classmethod
    def with_default_menu(cls) -> KioskStore:
        return cls(menu_items=DEFAULT_MENU)

    def list_menu(self, only_available: bool = True) -> list[MenuItem]:
        items: Iterable[MenuItem] = self._menu.values()
        if only_available:
            items = [item for item in items if item.is_available]
        return sorted(items, key=lambda item: item.id)

    def get_menu_item(self, menu_item_id: int) -> MenuItem | None:
        return self._menu.get(menu_item_id)

    def create_order(self, note: str | None = None) -> Order:
        order_id = self._next_order_id
        self._next_order_id += 1

        order = Order(id=order_id, note=note)
        self._orders[order_id] = order
        return order

    def list_orders(self, status: OrderStatus | None = None) -> list[Order]:
        orders: Iterable[Order] = self._orders.values()
        if status is not None:
            orders = [order for order in orders if order.status == status]
        return sorted(orders, key=lambda order: order.id)

    def get_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def add_item(
        self,
        order_id: int,
        menu_item_id: int,
        quantity: int,
        options: list[str] | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        menu_item = self._menu.get(menu_item_id)
        if menu_item is None:
            raise ValueError("Menu item not found")
        if not menu_item.is_available:
            raise ValueError("Menu item is not available")

        order_item = OrderItem(
            menu_item_id=menu_item.id,
            name=menu_item.name,
            unit_price=menu_item.price,
            quantity=quantity,
            options=options or [],
        )
        order.items.append(order_item)
        return order

    def draw_random_discount_menu(self) -> RandomDiscountMenuResult:
        """
        메뉴 중 하나와 할인율을 랜덤으로 뽑아 추천 결과를 만듬
        주문에 바로 추가하지 않고 추천 결과만 반환
        사용자에게 추가 여부를 확인
        """
        available_items = self.list_menu(only_available=True)
        if not available_items:
            raise ValueError("No available menu items")

        menu_item = random.choice(available_items)
        discount_rate = random.choice(RANDOM_DISCOUNT_RATES)
        discounted_price = menu_item.price * (100 - discount_rate) // 100

        return RandomDiscountMenuResult(
            menu_item=menu_item,
            discount_rate=discount_rate,
            original_price=menu_item.price,
            discounted_price=discounted_price,
        )

    def add_discounted_menu(
        self,
        order_id: int,
        result: RandomDiscountMenuResult,
    ) -> None:
        """
         추천 결과를 현재 주문에 할인된 가격으로 추가
        """
        order = self._require_order(order_id)

        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")

        order_item = OrderItem(
            menu_item_id=result.menu_item.id,
            name=f"{result.menu_item.name} (오늘의 랜덤 할인)",
            unit_price=result.discounted_price,
            quantity=1,
            options=[
                f"{result.discount_rate}% 할인",
                f"원가 {result.original_price}원",
            ],
        )
        order.items.append(order_item)

    def remove_item(self, order_id: int, line_index: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if line_index < 1 or line_index > len(order.items):
            raise ValueError("Line item not found")

        order.items.pop(line_index - 1)
        return order

    def cancel_order(self, order_id: int) -> Order:
        order = self._require_order(order_id)
        if order.status is OrderStatus.CANCELED:
            return order
        if order.status is OrderStatus.PAID:
            raise ValueError("Paid order cannot be canceled")

        order.status = OrderStatus.CANCELED
        order.canceled_at = utc_now()
        return order

    def pay_order(self, order_id: int, method: str, amount: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if not order.items:
            raise ValueError("Order has no items")
        if amount != order.total:
            raise ValueError("Payment amount does not match total")

        order.status = OrderStatus.PAID
        order.paid_at = utc_now()
        order.payment = Payment(method=method, amount=amount, paid_at=order.paid_at)
        return order

    def _require_order(self, order_id: int) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        return order
