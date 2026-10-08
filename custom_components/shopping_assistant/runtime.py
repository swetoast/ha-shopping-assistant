"""Runtime object tying settings, storage and OpenFoodFacts together."""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable
from dataclasses import dataclass, field
import logging
import os
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .api import (
    Credentials,
    OFFAuthError,
    OFFError,
    OFFRateLimitError,
    OpenFoodFactsClient,
    build_submission,
    message_ids,
    parse_product,
)
from .const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_OFF_SUBMISSION,
    CONF_ENABLE_WEBHOOK,
    CONF_LANGUAGE_PRIORITY,
    CONF_OFF_PASSWORD,
    CONF_OFF_TEST_MODE,
    CONF_OFF_USERNAME,
    CONF_SHOW_NOTIFICATIONS,
    CONF_TRACK_EXPIRY,
    CONF_TRACK_PRICES,
    CONF_WEBHOOK_LOCAL_ONLY,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_OPTIONS,
    DOMAIN,
    DUPLICATE_SCAN_SECONDS,
    EVENT_LOOKUP_COMPLETED,
    EVENT_MISSING_PRODUCT,
    EVENT_OFF_SUBMITTED,
    EVENT_PRODUCT_SCANNED,
    SIGNAL_UPDATE,
)
from .product_database import SOURCE_MANUAL, SOURCE_OFF, ProductData, ProductDatabase
from .shopping import ListItem, ShoppingList, describe_item

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def _read_base64(path: str) -> str | None:
    """Return a file as base64, or None if it does not exist (executor)."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode("ascii")


def parse_languages(value: Any) -> list[str]:
    """Return a language priority list from a list or comma-separated string."""
    if isinstance(value, str):
        value = value.split(",")
    if isinstance(value, (list, tuple)):
        languages = [str(item).strip().lower() for item in value if str(item).strip()]
        if languages:
            return languages
    return list(DEFAULT_LANGUAGE_PRIORITY)


@dataclass(frozen=True, slots=True)
class Settings:
    """Options of the config entry with defaults applied."""

    contact_email: str
    languages: tuple[str, ...]
    auto_add: bool
    show_notifications: bool
    track_prices: bool
    track_expiry: bool
    enable_webhook: bool
    webhook_local_only: bool
    off_submission: bool
    off_username: str
    off_password: str
    off_test_mode: bool

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> Settings:
        """Build from config entry options."""
        opts = {**DEFAULT_OPTIONS, **options}
        return cls(
            contact_email=str(opts[CONF_CONTACT_EMAIL]).strip(),
            languages=tuple(parse_languages(opts[CONF_LANGUAGE_PRIORITY])),
            auto_add=bool(opts[CONF_AUTO_ADD_TO_SHOPPING_LIST]),
            show_notifications=bool(opts[CONF_SHOW_NOTIFICATIONS]),
            track_prices=bool(opts[CONF_TRACK_PRICES]),
            track_expiry=bool(opts[CONF_TRACK_EXPIRY]),
            enable_webhook=bool(opts[CONF_ENABLE_WEBHOOK]),
            webhook_local_only=bool(opts[CONF_WEBHOOK_LOCAL_ONLY]),
            off_submission=bool(opts[CONF_ENABLE_OFF_SUBMISSION]),
            off_username=str(opts[CONF_OFF_USERNAME] or "").strip(),
            off_password=str(opts[CONF_OFF_PASSWORD] or ""),
            off_test_mode=bool(opts[CONF_OFF_TEST_MODE]),
        )


@dataclass(slots=True)
class ApiHealth:
    """Outcome of OpenFoodFacts requests. ``ok`` reflects the latest request."""

    ok: bool = True
    error_count: int = 0
    rate_limited_count: int = 0
    last_error: str | None = None
    last_error_time: str | None = None
    last_success_time: str | None = None

    def success(self) -> None:
        """Record a successful request."""
        self.ok = True
        self.last_success_time = dt_util.utcnow().isoformat()

    def failure(self, error: OFFError) -> None:
        """Record a failed request."""
        self.ok = False
        if isinstance(error, OFFRateLimitError):
            self.rate_limited_count += 1
        else:
            self.error_count += 1
        self.last_error = str(error)
        self.last_error_time = dt_util.utcnow().isoformat()


@dataclass(slots=True)
class ShoppingAssistant:
    """Everything one loaded config entry needs at runtime."""

    hass: HomeAssistant
    entry: ConfigEntry
    settings: Settings
    db: ProductDatabase
    client: OpenFoodFactsClient
    health: ApiHealth = field(default_factory=ApiHealth)
    _locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _recent_scans: dict[str, float] = field(default_factory=dict)
    _refreshing: set[str] = field(default_factory=set)

    @property
    def shopping(self) -> ShoppingList:
        """Return the shopping list."""
        return self.db.shopping

    def describe(self, item: ListItem) -> dict[str, Any]:
        """Return a list item with the details of its product."""
        return describe_item(item, self.db.get(item.ean) if item.ean else None)

    @callback
    def _health_changed(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # Lookup -----------------------------------------------------------------

    async def async_lookup(
        self, ean: str, *, force_refresh: bool = False
    ) -> tuple[ProductData | None, str]:
        """Resolve a barcode to a product.

        Returns (product, source) where source is one of local, openfoodfacts,
        cached_missing, missing, rate_limited or error. Concurrent lookups of
        the same barcode wait for each other, so only one request is sent.
        """
        async with self._locks.setdefault(ean, asyncio.Lock()):
            product = self.db.get(ean)
            if product and product.is_named and not force_refresh:
                self._schedule_refresh(product)
                return product, "local"
            if not force_refresh and self.db.is_recently_unknown(ean):
                return None, "cached_missing"
            return await self._async_fetch(ean)

    async def _async_fetch(self, ean: str) -> tuple[ProductData | None, str]:
        try:
            raw = await self.client.async_get_product(ean, self.settings.languages)
        except OFFError as err:
            _LOGGER.warning("OpenFoodFacts lookup of %s failed: %s", ean, err)
            self.health.failure(err)
            self._health_changed()
            return None, "rate_limited" if isinstance(err, OFFRateLimitError) else "error"
        self.health.success()
        self._health_changed()

        product = parse_product(ean, raw, self.settings.languages) if raw else None
        if product is None:
            if (existing := self.db.get(ean)) and existing.is_named:
                # Named locally but unknown to OFF (forced refresh): keep it.
                return existing, "local"
            unknown = self.db.mark_unknown(ean)
            self.hass.bus.async_fire(
                EVENT_MISSING_PRODUCT,
                {"ean": ean, "source": SOURCE_OFF, "seen_count": unknown.seen_count},
            )
            self.hass.bus.async_fire(
                EVENT_LOOKUP_COMPLETED,
                {"ean": ean, "found": False, "name": None, "source": SOURCE_OFF},
            )
            self._notify_missing(ean)
            return None, "missing"

        product = self.db.upsert_from_off(product)
        self.hass.bus.async_fire(
            EVENT_LOOKUP_COMPLETED,
            {"ean": ean, "found": True, "name": product.product_name, "source": SOURCE_OFF},
        )
        return product, SOURCE_OFF

    @callback
    def _schedule_refresh(self, product: ProductData) -> None:
        """Refresh stale OpenFoodFacts data in the background."""
        if not product.needs_refresh() or product.ean in self._refreshing:
            return
        self._refreshing.add(product.ean)

        async def _refresh() -> None:
            try:
                await self.async_lookup(product.ean, force_refresh=True)
            finally:
                self._refreshing.discard(product.ean)

        self.entry.async_create_background_task(
            self.hass, _refresh(), f"{DOMAIN} refresh {product.ean}"
        )

    # Scanning ---------------------------------------------------------------

    def _is_duplicate(self, ean: str) -> bool:
        now = time.monotonic()
        self._recent_scans = {
            key: stamp
            for key, stamp in self._recent_scans.items()
            if now - stamp < DUPLICATE_SCAN_SECONDS
        }
        if ean in self._recent_scans:
            return True
        self._recent_scans[ean] = now
        return False

    async def async_process_scan(
        self,
        ean: str,
        *,
        origin: str,
        add_to_list: bool | None = None,
        quantity: str | None = None,
    ) -> dict[str, Any]:
        """Handle one scan: look up, count, fire events, add to the list.

        add_to_list=None follows the auto-add option. Share and webhook scans
        of the same barcode within a few seconds are ignored.
        """
        if origin != "service" and self._is_duplicate(ean):
            _LOGGER.debug("Ignoring repeated scan of %s", ean)
            return {"ean": ean, "duplicate": True}

        product, source = await self.async_lookup(ean)
        self.db.record_scan(ean, source)
        name = product.product_name if product else None
        self.hass.bus.async_fire(
            EVENT_PRODUCT_SCANNED,
            {"ean": ean, "name": name, "source": source, "origin": origin},
        )

        result: dict[str, Any] = {
            "ean": ean,
            "name": name,
            "source": source,
            "added_to_shopping_list": False,
        }
        if add_to_list is None:
            add_to_list = self.settings.auto_add
        if product and add_to_list:
            item = self.shopping.add(name, ean=ean, quantity=quantity)
            result |= {"added_to_shopping_list": True, "item": item.to_dict()}
            self._notify(f"Added '{name}' to the shopping list", f"{DOMAIN}_added")
        return result

    # Notifications ----------------------------------------------------------

    @callback
    def _notify(self, message: str, notification_id: str, title: str = "Shopping Assistant") -> None:
        if self.settings.show_notifications:
            persistent_notification.async_create(
                self.hass, message, title=title, notification_id=notification_id
            )

    @callback
    def _notify_missing(self, ean: str) -> None:
        submit = (
            "  submit_to_openfoodfacts: true\n" if self.settings.off_submission else ""
        )
        message = (
            f"OpenFoodFacts has no product for barcode `{ean}`.\n\n"
            "Name the last scanned item:\n\n"
            "```yaml\n"
            "action: shopping_assistant.name_last_unknown\n"
            "data:\n"
            '  name: "Product name"\n'
            "```\n\n"
            "Or add details for this barcode:\n\n"
            "```yaml\n"
            "action: shopping_assistant.update_product\n"
            "data:\n"
            f'  ean: "{ean}"\n'
            '  name: "Product name"\n'
            '  brands: ""\n'
            '  quantity: ""\n'
            "  add_to_shopping_list: true\n"
            f"{submit}"
            "```"
        )
        self._notify(message, self.missing_notification_id(ean), "Shopping Assistant: unknown product")

    @staticmethod
    def missing_notification_id(ean: str) -> str:
        """Return the notification id used for a missing barcode."""
        return f"{DOMAIN}_missing_{ean}"

    @callback
    def dismiss_missing(self, ean: str) -> None:
        """Dismiss the missing-product notification for a barcode."""
        persistent_notification.async_dismiss(self.hass, self.missing_notification_id(ean))

    # OpenFoodFacts contribution ---------------------------------------------

    def _credentials(self, username: str | None, password: str | None) -> Credentials:
        if not self.settings.off_submission:
            raise ServiceValidationError(
                "OpenFoodFacts submission is disabled; enable it in the Shopping Assistant options"
            )
        username = (username or self.settings.off_username).strip()
        password = password or self.settings.off_password
        if not username or not password:
            raise ServiceValidationError(
                "An OpenFoodFacts username and password are required"
            )
        return Credentials(username, password)

    async def _async_contribute(
        self, ean: str, kind: str, request: Awaitable[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run a write request, fire the result event and map errors."""
        result: dict[str, Any] = {
            "ean": ean,
            "kind": kind,
            "test_mode": self.settings.off_test_mode,
        }
        try:
            payload = await request
        except OFFError as err:
            result |= {"ok": False, "error": str(err)}
            self.hass.bus.async_fire(EVENT_OFF_SUBMITTED, result)
            if not isinstance(err, OFFAuthError):
                self.health.failure(err)
                self._health_changed()
            raise HomeAssistantError(str(err)) from err
        result |= {
            "ok": True,
            "status": payload.get("status"),
            "result": (payload.get("result") or {}).get("id"),
            "warnings": message_ids(payload, "warnings") + message_ids(payload, "errors"),
        }
        self.hass.bus.async_fire(EVENT_OFF_SUBMITTED, result)
        _LOGGER.info(
            "Sent %s for %s to OpenFoodFacts%s: %s",
            kind,
            ean,
            " (test server)" if self.settings.off_test_mode else "",
            result["result"] or result["status"],
        )
        return result

    async def async_submit(
        self,
        ean: str,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Submit the details the user entered for a product to OpenFoodFacts.

        Only edited fields are sent, so data that came from OpenFoodFacts is
        never written back. Text goes in the first preferred language.
        """
        credentials = self._credentials(username, password)
        product = self.db.get(ean)
        if product is None or not product.is_named:
            raise ServiceValidationError(
                f"No named product for {ean}; add details with shopping_assistant.update_product first"
            )
        language = self.settings.languages[0]
        fields = build_submission(product, language=language, new_product=False)
        if not fields:
            raise ServiceValidationError(
                f"Nothing to submit for {ean}: only details entered with "
                "shopping_assistant.update_product are sent"
            )

        async def _write() -> dict[str, Any]:
            new_product = product.source == SOURCE_MANUAL and not (
                await self.client.async_product_exists(ean)
            )
            return await self.client.async_write_product(
                ean,
                build_submission(product, language=language, new_product=new_product),
                tags_lc=language,
                credentials=credentials,
            )

        result = await self._async_contribute(ean, "product", _write())
        return result | {"submitted_fields": sorted(fields), "language": language}

    async def async_upload_image(
        self,
        ean: str,
        image_path: str,
        *,
        image_field: str | None,
        language: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Upload a product photo to OpenFoodFacts."""
        credentials = self._credentials(username, password)
        if not self.hass.config.is_allowed_path(image_path):
            raise ServiceValidationError(
                f"{image_path} is not allowed; add its folder to allowlist_external_dirs"
            )
        image = await self.hass.async_add_executor_job(_read_base64, image_path)
        if image is None:
            raise ServiceValidationError(f"Image file not found: {image_path}")
        return await self._async_contribute(
            ean,
            "image",
            self.client.async_upload_image(
                ean,
                image,
                credentials=credentials,
                image_field=image_field,
                language=language,
            ),
        )

    async def async_shutdown(self) -> None:
        """Flush pending writes."""
        await self.db.async_flush()
