"""Webhook for external barcode scanners."""
from __future__ import annotations

from functools import partial
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import hdrs, web

from homeassistant.components import persistent_notification, webhook
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError

from .const import DATA_WEBHOOK_ID, DOMAIN
from .ean import extract_ean

if TYPE_CHECKING:
    from . import ShoppingAssistantConfigEntry

_LOGGER = logging.getLogger(__name__)

# Payload keys checked in order, from the query string, JSON or form body.
PAYLOAD_KEYS = ("ean", "barcode", "code", "text")
FORM_TYPES = frozenset({"application/x-www-form-urlencoded", "multipart/form-data"})


@callback
def webhook_url(hass: HomeAssistant, webhook_id: str) -> str:
    """Return the full webhook URL, or just the path if no URL is configured."""
    try:
        return webhook.async_generate_url(hass, webhook_id)
    except NoURLAvailableError:
        return webhook.async_generate_path(webhook_id)


async def _read_barcode_text(request: web.Request) -> str:
    """Return the first barcode-like value from query, JSON, form or plain body."""
    values: dict[str, Any] = dict(request.query)
    if request.body_exists:
        content_type = request.headers.get(hdrs.CONTENT_TYPE, "").split(";")[0]
        content_type = content_type.strip().lower()
        if content_type == "application/json":
            try:
                body = await request.json()
            except ValueError:
                body = None
            if isinstance(body, dict):
                values.update(body)
            elif body is not None:
                values.setdefault("text", body)
        elif content_type in FORM_TYPES:
            values.update(await request.post())
        else:
            values.setdefault("text", await request.text())
    return next(
        (str(values[key]) for key in PAYLOAD_KEYS if values.get(key) not in (None, "")),
        "",
    )


async def _async_handle_webhook(
    entry: ShoppingAssistantConfigEntry,
    hass: HomeAssistant,
    webhook_id: str,
    request: web.Request,
) -> web.Response:
    """Look up a barcode posted by an external scanner."""
    ean = extract_ean(await _read_barcode_text(request))
    if ean is None:
        return web.json_response(
            {"status": "error", "message": "No valid EAN/UPC barcode found"},
            status=HTTPStatus.BAD_REQUEST,
        )
    result = await entry.runtime_data.async_process_scan(ean, origin="webhook")
    return web.json_response({"status": "ok", **result})


@callback
def async_setup_webhook(hass: HomeAssistant, entry: ShoppingAssistantConfigEntry) -> None:
    """Register the webhook, creating a permanent id on first use."""
    if not (webhook_id := entry.data.get(DATA_WEBHOOK_ID)):
        webhook_id = webhook.async_generate_id()
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, DATA_WEBHOOK_ID: webhook_id}
        )
        persistent_notification.async_create(
            hass,
            "Barcode scanners can send barcodes to:\n\n"
            f"`{webhook_url(hass, webhook_id)}`\n\n"
            "The address is also shown in the Shopping Assistant options.",
            title="Shopping Assistant webhook",
            notification_id=f"{DOMAIN}_webhook",
        )
    webhook.async_register(
        hass,
        DOMAIN,
        "Shopping Assistant",
        webhook_id,
        partial(_async_handle_webhook, entry),
        local_only=entry.runtime_data.settings.webhook_local_only,
        allowed_methods=(hdrs.METH_GET, hdrs.METH_POST, hdrs.METH_PUT),
    )
    entry.async_on_unload(partial(webhook.async_unregister, hass, webhook_id))
    _LOGGER.debug("Webhook registered")
