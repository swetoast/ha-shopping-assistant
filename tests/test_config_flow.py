"""Tests for the config and options flows."""
from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.shopping_assistant.const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_OFF_SUBMISSION,
    CONF_LANGUAGE_PRIORITY,
    DATA_APP_UUID,
    DOMAIN,
    SHARE_EVENT,
)

from .conftest import KNOWN_EAN


async def test_user_flow(hass: HomeAssistant, off_lookup: AsyncMock) -> None:
    """A real contact email is required and only one entry is allowed."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    user_input = {
        CONF_CONTACT_EMAIL: "someone@example.com",
        CONF_AUTO_ADD_TO_SHOPPING_LIST: True,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["errors"] == {CONF_CONTACT_EMAIL: "invalid_email"}

    user_input[CONF_CONTACT_EMAIL] = " toast@example.org "
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_CONTACT_EMAIL] == "toast@example.org"
    assert len(result["data"][DATA_APP_UUID]) == 32

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_reloads_once(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, off_lookup: AsyncMock
) -> None:
    """Options validate input, reload the entry and never duplicate listeners."""
    for _ in range(2):
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        options = {**loaded_entry.options, CONF_LANGUAGE_PRIORITY: "sv, en"}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**options, CONF_LANGUAGE_PRIORITY: "swedish"}
        )
        assert result["errors"] == {CONF_LANGUAGE_PRIORITY: "invalid_language"}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**options, CONF_ENABLE_OFF_SUBMISSION: True}
        )
        assert result["errors"] == {"base": "credentials_required"}
        result = await hass.config_entries.options.async_configure(result["flow_id"], options)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    assert loaded_entry.options[CONF_LANGUAGE_PRIORITY] == ["sv", "en"]
    hass.bus.async_fire(SHARE_EVENT, {"text": KNOWN_EAN})
    await hass.async_block_till_done()
    assert off_lookup.call_count == 1
    assert hass.states.get("sensor.shopping_assistant_statistics").state == "1"
