"""Binary sensor for Shopping Assistant."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ShoppingAssistantEntity
from .runtime import ShoppingAssistant

if TYPE_CHECKING:
    from . import ShoppingAssistantConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShoppingAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the API problem sensor."""
    async_add_entities([ApiProblemSensor(entry.runtime_data)])


class ApiProblemSensor(ShoppingAssistantEntity, BinarySensorEntity):
    """On while the latest OpenFoodFacts request failed."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, assistant: ShoppingAssistant) -> None:
        """Initialize."""
        super().__init__(assistant, "api_problem", "api_diagnostic")

    @property
    def is_on(self) -> bool:
        """Return True if the last request failed."""
        return not self._assistant.health.ok

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return error details."""
        health = self._assistant.health
        attrs: dict[str, Any] = {
            "api_available": health.ok,
            "error_count": health.error_count,
            "rate_limited_count": health.rate_limited_count,
        }
        for key in ("last_error", "last_error_time", "last_success_time"):
            if (value := getattr(health, key)) is not None:
                attrs[key] = value
        return attrs
