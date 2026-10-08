"""Sensors for Shopping Assistant."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EXPIRY_WARNING_DAYS, MAX_UNKNOWNS_IN_ATTRIBUTES
from .entity import ShoppingAssistantEntity
from .product_database import ProductData
from .runtime import ShoppingAssistant

if TYPE_CHECKING:
    from . import ShoppingAssistantConfigEntry

EXPIRING_SUFFIX = "expiring_soon"

# Product attributes exposed per shopping list item.
SHOPPING_LIST_ATTRIBUTES: tuple[str, ...] = (
    "ean",
    "product_name",
    "brands",
    "quantity",
    "shopping_list_quantity",
    "added_to_list_at",
    "image_url",
    "image_small_url",
    "nutrition_grades",
    "eco_score_grade",
    "nova_group",
    "ingredients_analysis_vegan",
    "ingredients_analysis_vegetarian",
    "ingredients_analysis_palm_oil_free",
    "nutrition_per",
    "nutrition_preparation",
    "energy_kcal",
    "fat",
    "carbohydrates",
    "proteins",
    "serving_size",
    "calcium",
    "iron",
    "vitamin_c",
    "packaging",
    "carbon_footprint",
    "alcohol",
    "caffeine",
    "current_price",
    "price_currency",
    "expiry_date",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShoppingAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    assistant = entry.runtime_data
    entities: list[SensorEntity] = [
        StatisticsSensor(assistant),
        UnknownProductsSensor(assistant),
        ShoppingListSensor(assistant),
    ]
    if assistant.settings.track_expiry:
        entities.append(ExpiringSoonSensor(assistant))
    else:
        registry = er.async_get(hass)
        unique_id = f"{entry.entry_id}_{EXPIRING_SUFFIX}"
        if entity_id := registry.async_get_entity_id("sensor", DOMAIN, unique_id):
            registry.async_remove(entity_id)
    async_add_entities(entities)


class StatisticsSensor(ShoppingAssistantEntity, SensorEntity):
    """Total scans, with hit counts as attributes."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, assistant: ShoppingAssistant) -> None:
        """Initialize."""
        super().__init__(assistant, "statistics", "stats")

    @property
    def native_value(self) -> int:
        """Return the number of scans."""
        return self._assistant.db.statistics["total_scans"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return statistics."""
        db = self._assistant.db
        stats = db.statistics
        return {
            "total_mappings": sum(1 for p in db.products.values() if p.is_named),
            "unknown_products": len(db.unknowns),
            "total_scans": stats["total_scans"],
            "openfoodfacts_hits": stats["openfoodfacts_hits"],
            "local_hits": stats["local_hits"],
            "unknown_scans": stats["unknown_scans"],
            "last_scan": stats["last_scan"],
            "last_scan_time": stats["last_scan_time"],
        }


class UnknownProductsSensor(ShoppingAssistantEntity, SensorEntity):
    """Barcodes OpenFoodFacts does not know."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"unknowns"})

    def __init__(self, assistant: ShoppingAssistant) -> None:
        """Initialize."""
        super().__init__(assistant, "unknown_products", "unknowns")

    @property
    def native_value(self) -> int:
        """Return the number of unknown barcodes."""
        return len(self._assistant.db.unknowns)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the most frequently scanned unknown barcodes."""
        db = self._assistant.db
        unknowns = sorted(db.unknowns.values(), key=lambda u: u.seen_count, reverse=True)
        return {
            "unknowns": [u.to_dict() for u in unknowns[:MAX_UNKNOWNS_IN_ATTRIBUTES]],
            "total_unknown": len(unknowns),
            "last_missing_ean": db.last_missing_ean,
        }


class ShoppingListSensor(ShoppingAssistantEntity, SensorEntity):
    """Products currently on the shopping list."""

    _unrecorded_attributes = frozenset({"products"})

    def __init__(self, assistant: ShoppingAssistant) -> None:
        """Initialize."""
        super().__init__(assistant, "shopping_list", "shopping_list")

    @property
    def native_value(self) -> int:
        """Return the number of listed products."""
        return len(self._assistant.db.shopping_list())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the listed products."""
        products = [
            {key: getattr(p, key) for key in SHOPPING_LIST_ATTRIBUTES}
            for p in self._assistant.db.shopping_list()
        ]
        return {"products": products, "count": len(products)}


class ExpiringSoonSensor(ShoppingAssistantEntity, SensorEntity):
    """Products expiring within a week (expired ones included)."""

    _unrecorded_attributes = frozenset({"products"})

    def __init__(self, assistant: ShoppingAssistant) -> None:
        """Initialize."""
        super().__init__(assistant, "expiring_soon", EXPIRING_SUFFIX)

    def _expiring(self) -> list[tuple[ProductData, int]]:
        return self._assistant.db.expiring_within(EXPIRY_WARNING_DAYS, dt_util.now().date())

    @property
    def native_value(self) -> int:
        """Return how many products expire soon."""
        return len(self._expiring())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the products, soonest first."""
        return {
            "products": [
                {
                    "ean": product.ean,
                    "product_name": product.product_name,
                    "expiry_date": product.expiry_date,
                    "days_left": days_left,
                }
                for product, days_left in self._expiring()
            ]
        }

    async def async_added_to_hass(self) -> None:
        """Also refresh just after midnight, when days_left changes."""
        await super().async_added_to_hass()

        @callback
        def _midnight(_: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(self.hass, _midnight, hour=0, minute=0, second=5)
        )
