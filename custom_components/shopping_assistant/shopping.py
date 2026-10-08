"""The shopping list Shopping Assistant keeps itself.

Each entry is a ListItem. A new field on ListItem is stored, shown in the
shopping list sensor and returned by get_shopping_list without further
changes. Add it to UPDATABLE_FIELDS to let update_shopping_list_item set it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from homeassistant.util import dt as dt_util

from .storage import Record

if TYPE_CHECKING:
    from .product_database import ProductData


def _utcnow() -> str:
    return dt_util.utcnow().isoformat()


@dataclass(slots=True)
class ListItem(Record):
    """One thing to buy: a scanned product or free text."""

    name: str
    ean: str | None = None
    quantity: str | None = None
    note: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    added_at: str = field(default_factory=_utcnow)


# Fields update_shopping_list_item may change.
UPDATABLE_FIELDS: tuple[str, ...] = ("name", "quantity", "note")

# Product details shown with a listed product. The product's own net
# quantity is renamed so it does not clash with how many to buy.
PRODUCT_DETAILS: dict[str, str] = {
    "brands": "brands",
    "quantity": "net_quantity",
    "image_url": "image_url",
    "image_small_url": "image_small_url",
    "nutrition_grades": "nutrition_grades",
    "eco_score_grade": "eco_score_grade",
    "nova_group": "nova_group",
    "ingredients_analysis_vegan": "ingredients_analysis_vegan",
    "ingredients_analysis_vegetarian": "ingredients_analysis_vegetarian",
    "ingredients_analysis_palm_oil_free": "ingredients_analysis_palm_oil_free",
    "current_price": "current_price",
    "price_currency": "price_currency",
    "expiry_date": "expiry_date",
}


def describe_item(item: ListItem, product: ProductData | None) -> dict[str, Any]:
    """Return an item with the details of its product, for display."""
    result = item.to_dict()
    if product is not None:
        if product.is_named:
            result["name"] = product.product_name
        for attr, key in PRODUCT_DETAILS.items():
            if (value := getattr(product, attr)) is not None:
                result[key] = value
    return result


def _bumped(quantity: str | None) -> str | None:
    """Return a whole-number quantity plus one; other quantities stay as they are."""
    if quantity is None:
        return "2"
    return str(int(quantity) + 1) if quantity.isdigit() else quantity


class ShoppingList:
    """Ordered list of items; calls on_change after every change."""

    def __init__(self, on_change: Callable[[], None]) -> None:
        """Initialize."""
        self._on_change = on_change
        self.items: dict[str, ListItem] = {}

    def load(self, raw: Iterable[dict[str, Any]]) -> None:
        """Replace the items with stored ones."""
        items = (ListItem.from_dict(data) for data in raw if data.get("name"))
        self.items = {item.id: item for item in items}

    def dump(self) -> list[dict[str, Any]]:
        """Return the items for storage."""
        return [item.to_dict() for item in self.items.values()]

    def find(self, *, item_id: str | None = None, ean: str | None = None) -> ListItem | None:
        """Return the item with this id, or the first one for this barcode."""
        if item_id is not None:
            return self.items.get(item_id)
        return next((item for item in self.items.values() if item.ean == ean), None)

    def add(
        self,
        name: str,
        *,
        ean: str | None = None,
        quantity: str | None = None,
        note: str | None = None,
    ) -> ListItem:
        """Add an item. Adding one that is listed already raises its count.

        Products match by barcode and free text by name. An explicit quantity
        replaces the listed one; without one a whole number goes up by one.
        """
        if ean is not None:
            item = self.find(ean=ean)
        else:
            item = next(
                (
                    item
                    for item in self.items.values()
                    if item.ean is None and item.name.casefold() == name.casefold()
                ),
                None,
            )
        if item is None:
            item = ListItem(name=name, ean=ean, quantity=quantity, note=note)
            self.items[item.id] = item
        else:
            item.quantity = quantity if quantity is not None else _bumped(item.quantity)
            if note is not None:
                item.note = note
        self._on_change()
        return item

    def update(self, item: ListItem, values: dict[str, Any]) -> ListItem:
        """Change fields of an item. An empty string clears an optional field."""
        for key, value in values.items():
            if key in UPDATABLE_FIELDS and (value or key != "name"):
                setattr(item, key, value or None)
        self._on_change()
        return item

    def remove(self, items: Iterable[ListItem]) -> int:
        """Remove items; returns how many were removed."""
        count = sum(self.items.pop(item.id, None) is not None for item in items)
        if count:
            self._on_change()
        return count
