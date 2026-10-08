"""Keep the product database in sync with a Home Assistant to-do list."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.start import async_at_started

from .product_database import ProductData, ProductDatabase

_LOGGER = logging.getLogger(__name__)

TODO_DOMAIN = "todo"
RECONCILE_COOLDOWN = 2.0


def _same(summary: Any, name: str) -> bool:
    return str(summary or "").casefold() == name.casefold()


class ShoppingList:
    """Add products to a to-do entity and mirror its open items locally.

    Items are matched by product name. When an item is completed or removed
    in the to-do list, the product's in_shopping_list flag is cleared.
    """

    def __init__(self, hass: HomeAssistant, db: ProductDatabase, entity_id: str) -> None:
        """Initialize."""
        self._hass = hass
        self._db = db
        self.entity_id = entity_id
        self._debouncer: Debouncer[Any] = Debouncer(
            hass,
            _LOGGER,
            cooldown=RECONCILE_COOLDOWN,
            immediate=False,
            function=self.async_reconcile,
        )

    @property
    def available(self) -> bool:
        """Return True if the to-do entity exists and is available."""
        state = self._hass.states.get(self.entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    async def _call(
        self, service: str, data: dict[str, Any], *, response: bool = False
    ) -> Any:
        return await self._hass.services.async_call(
            TODO_DOMAIN,
            service,
            data,
            target={"entity_id": self.entity_id},
            blocking=True,
            return_response=response,
        )

    async def _open_items(self) -> list[dict[str, Any]]:
        result = await self._call("get_items", {"status": ["needs_action"]}, response=True)
        return list((result or {}).get(self.entity_id, {}).get("items", []))

    async def async_add(self, product: ProductData, quantity: str | None = None) -> None:
        """Add a product unless an open item with the same name exists."""
        if not self.available:
            raise HomeAssistantError(
                f"To-do list {self.entity_id} is not available; check the "
                "shopping list entity in the Shopping Assistant options"
            )
        items = await self._open_items()
        if not any(_same(item.get("summary"), product.product_name) for item in items):
            await self._call("add_item", {"item": product.product_name})
        self._db.set_in_shopping_list(product.ean, quantity)

    async def async_remove(self, eans: Iterable[str]) -> int:
        """Remove products from the to-do list and clear their flags."""
        listed = [p for ean in eans if (p := self._db.get(ean)) and p.in_shopping_list]
        if listed and self.available:
            items = await self._open_items()
            uids = [
                item["uid"]
                for item in items
                if item.get("uid")
                and any(_same(item.get("summary"), p.product_name) for p in listed)
            ]
            if uids:
                try:
                    await self._call("remove_item", {"item": uids})
                except HomeAssistantError as err:
                    _LOGGER.warning("Could not remove items from %s: %s", self.entity_id, err)
        return self._db.clear_shopping_list_flags(p.ean for p in listed)

    async def async_reconcile(self) -> None:
        """Clear flags for products no longer open in the to-do list."""
        listed = self._db.shopping_list()
        if not listed or not self.available:
            return
        try:
            items = await self._open_items()
        except HomeAssistantError as err:
            _LOGGER.debug("Cannot read %s: %s", self.entity_id, err)
            return
        self._db.clear_shopping_list_flags(
            p.ean
            for p in listed
            if not any(_same(item.get("summary"), p.product_name) for item in items)
        )

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start following the to-do entity; returns a stop callback."""

        @callback
        def _schedule(_: Event | HomeAssistant) -> None:
            self._debouncer.async_schedule_call()

        unsub_state = async_track_state_change_event(
            self._hass, [self.entity_id], _schedule
        )
        unsub_started = async_at_started(self._hass, _schedule)

        @callback
        def _stop() -> None:
            unsub_state()
            unsub_started()
            self._debouncer.async_shutdown()

        return _stop
