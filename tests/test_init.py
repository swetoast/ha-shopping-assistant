"""Integration tests for setup, scanning, services and the webhook."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.shopping_assistant.api import OFFRateLimitError
from custom_components.shopping_assistant.const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_ENABLE_WEBHOOK,
    CONF_LANGUAGE_PRIORITY,
    DATA_WEBHOOK_ID,
    DOMAIN,
    EVENT_PRODUCT_SCANNED,
    LEGACY_DOMAIN,
    LEGACY_STORAGE_KEY,
    SHARE_EVENT,
    STORAGE_KEY,
)

from .conftest import KNOWN_EAN, UNKNOWN_EAN, make_entry

NUTELLA = "Ferrero - Nutella hasselnotskram (400 g)"


async def _todo_items(hass: HomeAssistant) -> list[str]:
    result = await hass.services.async_call(
        "todo",
        "get_items",
        {"status": ["needs_action"]},
        target={"entity_id": "todo.shopping_list"},
        blocking=True,
        return_response=True,
    )
    return [item["summary"] for item in result["todo.shopping_list"]["items"]]


async def _share(hass: HomeAssistant, text: str) -> None:
    hass.bus.async_fire(SHARE_EVENT, {"text": text})
    await hass.async_block_till_done()


async def test_scan_adds_to_todo_and_syncs_back(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, off_lookup: AsyncMock
) -> None:
    """A shared barcode is looked up once, listed once and unflagged when completed."""
    scanned = async_capture_events(hass, EVENT_PRODUCT_SCANNED)

    await _share(hass, KNOWN_EAN)
    await _share(hass, KNOWN_EAN)  # repeated share within seconds is ignored

    assert off_lookup.call_count == 1
    assert [e.data["source"] for e in scanned] == ["openfoodfacts"]
    assert await _todo_items(hass) == [NUTELLA]
    assert hass.states.get("sensor.shopping_assistant_shopping_list").state == "1"
    assert hass.states.get("sensor.shopping_assistant_statistics").state == "1"

    # An explicit service scan is a local hit and does not duplicate the item.
    response = await hass.services.async_call(
        DOMAIN,
        "add_scanned_to_shopping_list",
        {"ean": KNOWN_EAN, "quantity": "2"},
        blocking=True,
        return_response=True,
    )
    assert response["source"] == "local"
    assert await _todo_items(hass) == [NUTELLA]
    assert off_lookup.call_count == 1

    # Completing the to-do item clears the product's shopping list flag.
    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": NUTELLA, "status": "completed"},
        target={"entity_id": "todo.shopping_list"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.shopping_assistant_shopping_list").state == "0"
    attrs = hass.states.get("sensor.shopping_assistant_statistics").attributes
    assert attrs["total_scans"] == 2
    assert attrs["local_hits"] == 1


async def test_unknown_then_mapping_keeps_data(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Unknown barcodes are cached; naming them or a known product keeps its data."""
    await _share(hass, UNKNOWN_EAN)
    assert hass.states.get("sensor.shopping_assistant_unknown_products").state == "1"

    await hass.services.async_call(
        DOMAIN, "add_last_missing_mapping", {"name": "Store milk"}, blocking=True
    )
    assert hass.states.get("sensor.shopping_assistant_unknown_products").state == "0"
    assert "Store milk" in await _todo_items(hass)

    await _share(hass, KNOWN_EAN)
    await hass.services.async_call(
        DOMAIN, "add_mapping", {"ean": KNOWN_EAN, "name": "My Nutella"}, blocking=True
    )
    product = loaded_entry.runtime_data.db.get(KNOWN_EAN)
    assert product.product_name == "My Nutella"
    assert product.fat == 30.9
    assert product.in_shopping_list
    assert product.source == "openfoodfacts+manual"


async def test_api_problem_and_service_responses(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, off_lookup: AsyncMock
) -> None:
    """The problem sensor follows the latest request; data services return responses."""
    off_lookup.side_effect = OFFRateLimitError("HTTP 503")
    response = await hass.services.async_call(
        DOMAIN, "lookup_product", {"ean": KNOWN_EAN}, blocking=True, return_response=True
    )
    assert response["source"] == "rate_limited"
    assert hass.states.get("binary_sensor.shopping_assistant_api_problem").state == "on"
    assert not loaded_entry.runtime_data.db.unknowns  # throttling is not "missing"

    off_lookup.side_effect = None
    off_lookup.return_value = None
    response = await hass.services.async_call(
        DOMAIN, "lookup_product", {"ean": UNKNOWN_EAN}, blocking=True, return_response=True
    )
    assert response == {"ean": UNKNOWN_EAN, "found": False, "source": "missing", "product": None}
    assert hass.states.get("binary_sensor.shopping_assistant_api_problem").state == "off"

    await hass.services.async_call(
        DOMAIN, "add_mapping", {"ean": "036000291452", "name": "Tea"}, blocking=True
    )
    export = await hass.services.async_call(
        DOMAIN, "export_mappings", {}, blocking=True, return_response=True
    )
    assert set(export["products"]) == {"0036000291452"}

    result = await hass.services.async_call(
        DOMAIN,
        "import_mappings",
        {"data": {"mappings": {KNOWN_EAN: {"name": "Imported"}}}, "merge": False},
        blocking=True,
        return_response=True,
    )
    assert result == {"imported_count": 1}
    assert set(loaded_entry.runtime_data.db.products) == {KNOWN_EAN}


async def test_webhook_is_stable_and_returns_json(
    hass: HomeAssistant, shopping_list: None, off_lookup: AsyncMock, hass_client_no_auth
) -> None:
    """The webhook keeps its id across reloads and answers with JSON."""
    entry = make_entry(**{CONF_ENABLE_WEBHOOK: True, CONF_AUTO_ADD_TO_SHOPPING_LIST: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    webhook_id = entry.data[DATA_WEBHOOK_ID]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data[DATA_WEBHOOK_ID] == webhook_id

    client = await hass_client_no_auth()
    resp = await client.post(f"/api/webhook/{webhook_id}", json={"barcode": KNOWN_EAN})
    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body["status"] == "ok"
    assert body["name"] == NUTELLA
    assert body["added_to_shopping_list"] is False

    resp = await client.get(f"/api/webhook/{webhook_id}?code=2026-10-08")
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_import_from_ean_reader(
    hass: HomeAssistant, shopping_list: None, off_lookup: AsyncMock, hass_storage
) -> None:
    """EAN Reader options pre-fill setup and its products are imported once."""
    hass_storage[LEGACY_STORAGE_KEY] = {
        "version": 3,
        "minor_version": 1,
        "key": LEGACY_STORAGE_KEY,
        "data": {"mappings": {KNOWN_EAN: {"name": "Old name"}}, "unknowns": {}},
    }
    MockConfigEntry(
        domain=LEGACY_DOMAIN,
        options={
            "contact_email": "toast@example.org",
            "show_images": True,
            CONF_LANGUAGE_PRIORITY: "de, en",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    schema = result["data_schema"].schema
    suggested = {
        str(key): key.description["suggested_value"]
        for key in schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested["contact_email"] == "toast@example.org"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "contact_email": "toast@example.org",
            "shopping_list_entity": "todo.shopping_list",
            "auto_add_to_shopping_list": True,
        },
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED
    assert entry.options[CONF_LANGUAGE_PRIORITY] == ["de", "en"]
    assert "show_images" not in entry.options
    assert entry.runtime_data.db.get(KNOWN_EAN).product_name == "Old name"
    assert hass_storage[STORAGE_KEY]["data"]["products"][KNOWN_EAN]["product_name"] == "Old name"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "legacy_integration")


async def test_card_is_installed_and_loaded(
    hass: HomeAssistant,
    frontend_urls: set[str],
    shopping_list: None,
    off_lookup: AsyncMock,
    hass_client_no_auth,
    config_dir: Path,
) -> None:
    """Without a www folder the card is copied there and served from the integration."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    installed = config_dir / "www" / "shopping-assistant" / "shopping-assistant-card.js"
    assert "shopping-assistant-card" in installed.read_text()
    assert frontend_urls == {"/shopping_assistant/shopping-assistant-card.js?v=2.0.0"}
    client = await hass_client_no_auth()
    resp = await client.get("/shopping_assistant/shopping-assistant-card.js")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == installed.read_text()


async def test_card_loads_from_www(
    hass: HomeAssistant,
    frontend_urls: set[str],
    shopping_list: None,
    off_lookup: AsyncMock,
    config_dir: Path,
) -> None:
    """With a www folder the card loads from /local and an old copy is replaced."""
    installed = config_dir / "www" / "shopping-assistant" / "shopping-assistant-card.js"
    installed.parent.mkdir(parents=True)
    installed.write_text("old")
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert frontend_urls == {"/local/shopping-assistant/shopping-assistant-card.js?v=2.0.0"}
    assert "shopping-assistant-card" in installed.read_text()
