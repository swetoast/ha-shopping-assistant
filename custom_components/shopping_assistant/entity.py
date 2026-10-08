"""Base entity for Shopping Assistant."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE
from .runtime import ShoppingAssistant


class ShoppingAssistantEntity(Entity):
    """Entity that refreshes whenever the product database changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, assistant: ShoppingAssistant, translation_key: str, unique_suffix: str) -> None:
        """Initialize."""
        self._assistant = assistant
        entry_id = assistant.entry.entry_id
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Shopping Assistant",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://world.openfoodfacts.org",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to data updates."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state)
        )
