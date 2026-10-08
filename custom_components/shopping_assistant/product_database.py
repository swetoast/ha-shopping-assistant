"""Local product database for Shopping Assistant."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    LEGACY_STORAGE_KEY,
    MAX_PRICE_HISTORY,
    REFRESH_AFTER_DAYS,
    SAVE_DELAY,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    UNKNOWN_PRODUCT_NAME,
    UNKNOWN_RETRY_SECONDS,
)
from .ean import normalize_ean

SOURCE_OFF = "openfoodfacts"
SOURCE_OFF_EDITED = "openfoodfacts+manual"
SOURCE_MANUAL = "manual"
SOURCE_LOCAL = "local"  # placeholder created by price/expiry tracking


def _utcnow() -> str:
    """Return the current UTC time as an ISO string."""
    return dt_util.utcnow().isoformat()


@dataclass(slots=True)
class ProductData:
    """Everything known about one product, from OpenFoodFacts and local edits."""

    ean: str
    product_name: str
    source: str

    # Basic info
    brands: str | None = None
    quantity: str | None = None
    categories: str | None = None
    generic_name: str | None = None
    localized_names: dict[str, str] = field(default_factory=dict)

    # Ingredients and allergens
    ingredients_text: str | None = None
    allergens: str | None = None
    traces: str | None = None
    additives: list[str] = field(default_factory=list)

    # Nutrition per 100 g / 100 ml (nutrition_per), as sold or prepared
    nutrition_grades: str | None = None
    nutrition_preparation: str | None = None
    nutrition_per: str | None = None
    energy_kcal: float | None = None
    energy_kj: float | None = None
    fat: float | None = None
    saturated_fat: float | None = None
    carbohydrates: float | None = None
    sugars: float | None = None
    fiber: float | None = None
    proteins: float | None = None
    salt: float | None = None
    sodium: float | None = None
    monounsaturated_fat: float | None = None
    polyunsaturated_fat: float | None = None
    trans_fat: float | None = None
    cholesterol: float | None = None
    omega_3_fat: float | None = None
    omega_6_fat: float | None = None
    vitamin_a: float | None = None
    vitamin_c: float | None = None
    vitamin_d: float | None = None
    vitamin_e: float | None = None
    vitamin_k: float | None = None
    vitamin_b1: float | None = None
    vitamin_b2: float | None = None
    vitamin_b6: float | None = None
    vitamin_b9: float | None = None
    vitamin_b12: float | None = None
    calcium: float | None = None
    iron: float | None = None
    magnesium: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    zinc: float | None = None
    alcohol: float | None = None
    caffeine: float | None = None

    # Serving
    serving_size: str | None = None
    serving_quantity: float | None = None

    # Packaging and sustainability
    packaging: str | None = None
    packaging_tags: list[str] = field(default_factory=list)
    recycling_instructions: str | None = None
    carbon_footprint: float | None = None  # kg CO2e per kg (Agribalyse)

    # Ingredients analysis: "yes", "no" or "maybe"
    ingredients_from_palm_oil: list[str] = field(default_factory=list)
    ingredients_analysis_vegan: str | None = None
    ingredients_analysis_vegetarian: str | None = None
    ingredients_analysis_palm_oil_free: str | None = None

    # Images
    image_url: str | None = None
    image_small_url: str | None = None
    image_front_url: str | None = None
    image_ingredients_url: str | None = None
    image_nutrition_url: str | None = None

    # Labels and scores
    labels: list[str] = field(default_factory=list)
    eco_score_grade: str | None = None
    nova_group: int | None = None

    # Origins
    origins: str | None = None
    manufacturing_places: str | None = None
    countries: str | None = None
    stores: str | None = None

    # OpenFoodFacts metadata
    completeness: float | None = None
    last_modified_t: int | None = None
    fetched_at: str | None = None

    # Product details the user entered; these are what gets submitted to OFF
    edited_fields: list[str] = field(default_factory=list)

    # Local data (kept when OpenFoodFacts data is refreshed)
    first_seen: str = field(default_factory=_utcnow)
    last_updated: str = field(default_factory=_utcnow)
    scan_count: int = 0
    prices: list[dict[str, Any]] = field(default_factory=list)
    current_price: float | None = None
    price_currency: str | None = None
    expiry_date: str | None = None
    expiry_set_at: str | None = None
    notes: str | None = None
    in_shopping_list: bool = False
    shopping_list_quantity: str | None = None
    added_to_list_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductData:
        """Build from stored data, ignoring keys this version does not know."""
        known = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in known}
        values.setdefault("product_name", UNKNOWN_PRODUCT_NAME)
        values.setdefault("source", SOURCE_MANUAL)
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """Serialize, leaving out empty values."""
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None and value not in ("", [], {})
        }

    @property
    def is_named(self) -> bool:
        """Return True if the product has a real name."""
        return bool(self.product_name) and self.product_name != UNKNOWN_PRODUCT_NAME

    def needs_refresh(self) -> bool:
        """Return True if unedited OpenFoodFacts data is due for a refresh."""
        if self.source != SOURCE_OFF:
            return False
        fetched = dt_util.parse_datetime(self.fetched_at or "")
        return fetched is None or dt_util.utcnow() - fetched > timedelta(
            days=REFRESH_AFTER_DAYS
        )


# Fields owned by the user; an OpenFoodFacts refresh never overwrites them.
LOCAL_FIELDS: tuple[str, ...] = (
    "first_seen",
    "scan_count",
    "prices",
    "current_price",
    "price_currency",
    "expiry_date",
    "expiry_set_at",
    "notes",
    "in_shopping_list",
    "shopping_list_quantity",
    "added_to_list_at",
)

# Nutrients (per 100 g / 100 ml) the user may enter.
EDITABLE_NUTRIENTS: frozenset[str] = frozenset(
    {
        "energy_kcal",
        "energy_kj",
        "fat",
        "saturated_fat",
        "carbohydrates",
        "sugars",
        "fiber",
        "proteins",
        "salt",
        "sodium",
    }
)

# Fields the update_product and submit services may change.
EDITABLE_FIELDS: frozenset[str] = (
    frozenset(
        {
            "product_name",
            "brands",
            "quantity",
            "categories",
            "ingredients_text",
            "allergens",
            "traces",
            "labels",
            "stores",
            "origins",
            "packaging",
            "notes",
        }
    )
    | EDITABLE_NUTRIENTS
)


@dataclass(slots=True)
class UnknownProduct:
    """A barcode OpenFoodFacts does not know."""

    ean: str
    first_seen: str = field(default_factory=_utcnow)
    last_seen: str = field(default_factory=_utcnow)
    seen_count: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnknownProduct:
        """Build from stored data, ignoring unknown keys."""
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})

    def to_dict(self) -> dict[str, Any]:
        """Serialize."""
        return asdict(self)


def _default_statistics() -> dict[str, Any]:
    return {
        "total_scans": 0,
        "openfoodfacts_hits": 0,
        "local_hits": 0,
        "unknown_scans": 0,
        "last_scan": None,
        "last_scan_time": None,
    }


def _storage_key(ean: Any) -> str:
    code = str(ean)
    return normalize_ean(code) if code.isdigit() else code


def _migrate_product(ean: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Bring one stored product up to the current layout."""
    product = dict(raw)
    if "product_name" not in product:
        # Pre-ProductData layout: {"name": ..., "ingredients": ..., "updated_at": ...}
        product["product_name"] = product.pop("name", None) or UNKNOWN_PRODUCT_NAME
        if "ingredients" in product:
            product["ingredients_text"] = product.pop("ingredients")
        if updated := product.pop("updated_at", None):
            product.setdefault("first_seen", updated)
            product.setdefault("last_updated", updated)
    product["ean"] = ean
    product.setdefault("source", SOURCE_MANUAL)

    names = dict(product.get("localized_names") or {})
    for key in [key for key in product if key.startswith("product_name_")]:
        if value := product.pop(key):
            names.setdefault(key.removeprefix("product_name_"), value)
    if names:
        product["localized_names"] = names
    product.pop("favorite", None)
    product.pop("ingredients_analysis_palm_oil", None)

    if "fetched_at" not in product:
        # Before 1.2.0 the vegan/vegetarian/palm oil analysis was parsed
        # wrongly and carbon_footprint used another unit. Reset them; the
        # product is refreshed from OpenFoodFacts on its next scan.
        product.pop("carbon_footprint", None)
        if str(product["source"]).startswith(SOURCE_OFF):
            for key in (
                "ingredients_analysis_vegan",
                "ingredients_analysis_vegetarian",
                "ingredients_analysis_palm_oil_free",
            ):
                product[key] = "maybe"
    if product["source"] == SOURCE_MANUAL and "edited_fields" not in product:
        # Everything in a manual product was entered by the user.
        product["edited_fields"] = sorted(
            key for key in EDITABLE_FIELDS - set(LOCAL_FIELDS) if product.get(key)
        )
    return product


def migrate_storage(data: dict[str, Any]) -> dict[str, Any]:
    """Convert any earlier storage or export layout to the current one.

    Handles the 1.2.0 product layout, the older ``mappings`` layout (with its
    separate price history and expiry dicts) and a bare EAN -> mapping dict.
    """
    known_keys = ("products", "mappings", "unknowns", "statistics")
    legacy = data.get("mappings") or {}
    if not any(key in data for key in known_keys):
        legacy = data

    products: dict[str, dict[str, Any]] = {}
    for ean, raw in (data.get("products") or {}).items():
        if isinstance(raw, dict):
            key = _storage_key(ean)
            products.setdefault(key, _migrate_product(key, raw))

    prices = data.get("price_history") or {}
    expiry = data.get("expiry_tracking") or {}
    for ean, raw in legacy.items():
        key = _storage_key(ean)
        if not isinstance(raw, dict) or key in products:
            continue
        product = _migrate_product(key, raw)
        if history := prices.get(ean):
            product["prices"] = history[-MAX_PRICE_HISTORY:]
            product["current_price"] = history[-1].get("price")
            product["price_currency"] = history[-1].get("currency")
        if tracked := expiry.get(ean):
            product["expiry_date"] = tracked.get("expiry_date")
            product["expiry_set_at"] = tracked.get("set_at")
        products[key] = product

    unknowns = {
        _storage_key(ean): {**raw, "ean": _storage_key(ean)}
        for ean, raw in (data.get("unknowns") or {}).items()
        if isinstance(raw, dict) and _storage_key(ean) not in products
    }
    last_missing = data.get("last_missing_ean")
    return {
        "products": products,
        "unknowns": unknowns,
        "last_missing_ean": _storage_key(last_missing) if last_missing else None,
        "statistics": data.get("statistics") or {},
    }


class _ProductStore(Store[dict[str, Any]]):
    """Store that migrates older layouts on load."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        return migrate_storage(old_data)


class ProductDatabase:
    """Product database persisted in .storage/shopping_assistant_mappings."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._store = _ProductStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
        )
        self.products: dict[str, ProductData] = {}
        self.unknowns: dict[str, UnknownProduct] = {}
        self.last_missing_ean: str | None = None
        self.statistics: dict[str, Any] = _default_statistics()

    async def async_load(self) -> bool:
        """Load from disk; returns True if EAN Reader data was imported."""
        data = await self._store.async_load()
        imported = False
        if data is None:
            legacy = _ProductStore(
                self._hass,
                STORAGE_VERSION,
                LEGACY_STORAGE_KEY,
                minor_version=STORAGE_MINOR_VERSION,
            )
            imported = (data := await legacy.async_load()) is not None
        self._apply(data or {})
        if imported:
            await self.async_flush()
        return imported

    def _apply(self, data: dict[str, Any]) -> None:
        self.products = {
            ean: ProductData.from_dict({**raw, "ean": ean})
            for ean, raw in (data.get("products") or {}).items()
        }
        self.unknowns = {
            ean: UnknownProduct.from_dict({**raw, "ean": ean})
            for ean, raw in (data.get("unknowns") or {}).items()
        }
        self.last_missing_ean = data.get("last_missing_ean")
        self.statistics = {**_default_statistics(), **(data.get("statistics") or {})}

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "products": {ean: p.to_dict() for ean, p in self.products.items()},
            "unknowns": {ean: u.to_dict() for ean, u in self.unknowns.items()},
            "last_missing_ean": self.last_missing_ean,
            "statistics": self.statistics,
        }

    @callback
    def _changed(self) -> None:
        """Schedule a save and refresh entities."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)
        async_dispatcher_send(self._hass, SIGNAL_UPDATE)

    async def async_flush(self) -> None:
        """Write pending changes now (used on unload)."""
        await self._store.async_save(self._data_to_save())

    def _resolved(self, ean: str) -> None:
        self.unknowns.pop(ean, None)
        if self.last_missing_ean == ean:
            self.last_missing_ean = None

    def _placeholder(self, ean: str) -> ProductData:
        if (product := self.products.get(ean)) is None:
            product = ProductData(
                ean=ean, product_name=UNKNOWN_PRODUCT_NAME, source=SOURCE_LOCAL
            )
            self.products[ean] = product
        return product

    def get(self, ean: str) -> ProductData | None:
        """Return a product."""
        return self.products.get(ean)

    @callback
    def upsert_from_off(self, product: ProductData) -> ProductData:
        """Store fresh OpenFoodFacts data, keeping local fields."""
        if existing := self.products.get(product.ean):
            for name in LOCAL_FIELDS:
                setattr(product, name, getattr(existing, name))
        product.last_updated = _utcnow()
        self.products[product.ean] = product
        self._resolved(product.ean)
        self._changed()
        return product

    @callback
    def update_fields(self, ean: str, values: dict[str, Any]) -> ProductData:
        """Apply a partial edit, creating the product if needed."""
        product = self.products.get(ean)
        if product is None:
            product = ProductData(
                ean=ean, product_name=UNKNOWN_PRODUCT_NAME, source=SOURCE_MANUAL
            )
            self.products[ean] = product
        elif any(key not in LOCAL_FIELDS for key in values):
            # Product details changed: record that the data is no longer
            # only what OpenFoodFacts says (also stops automatic refresh).
            if product.source == SOURCE_LOCAL:
                product.source = SOURCE_MANUAL
            elif product.source == SOURCE_OFF:
                product.source = SOURCE_OFF_EDITED

        for key, value in values.items():
            if key in EDITABLE_FIELDS:
                setattr(product, key, value)
                if key not in LOCAL_FIELDS and key not in product.edited_fields:
                    product.edited_fields = [*product.edited_fields, key]
        product.last_updated = _utcnow()
        if product.is_named:
            self._resolved(ean)
        self._changed()
        return product

    @callback
    def delete(self, ean: str) -> bool:
        """Delete a product and its unknown entry."""
        removed = self.products.pop(ean, None) is not None
        removed = self.unknowns.pop(ean, None) is not None or removed
        if self.last_missing_ean == ean:
            self.last_missing_ean = None
        if removed:
            self._changed()
        return removed

    @callback
    def mark_unknown(self, ean: str) -> UnknownProduct:
        """Record that OpenFoodFacts does not know a barcode."""
        if unknown := self.unknowns.get(ean):
            unknown.last_seen = _utcnow()
            unknown.seen_count += 1
        else:
            unknown = self.unknowns[ean] = UnknownProduct(ean=ean)
        self.last_missing_ean = ean
        self._changed()
        return unknown

    def is_recently_unknown(self, ean: str) -> bool:
        """Return True if OpenFoodFacts missed this barcode within the retry window."""
        if (unknown := self.unknowns.get(ean)) is None:
            return False
        last_seen = dt_util.parse_datetime(unknown.last_seen)
        if last_seen is None:
            return False
        return (dt_util.utcnow() - last_seen).total_seconds() < UNKNOWN_RETRY_SECONDS

    @callback
    def record_scan(self, ean: str, source: str) -> None:
        """Update statistics for one scan."""
        stats = self.statistics
        stats["total_scans"] += 1
        stats["last_scan"] = ean
        stats["last_scan_time"] = _utcnow()
        counter = {
            "local": "local_hits",
            SOURCE_OFF: "openfoodfacts_hits",
            "missing": "unknown_scans",
            "cached_missing": "unknown_scans",
        }.get(source)
        if counter:
            stats[counter] += 1
        if product := self.products.get(ean):
            product.scan_count += 1
        self._changed()

    @callback
    def add_price(
        self, ean: str, price: float, currency: str, store: str | None
    ) -> ProductData:
        """Append a price entry."""
        product = self._placeholder(ean)
        product.prices = [
            *product.prices,
            {"price": price, "currency": currency, "store": store, "timestamp": _utcnow()},
        ][-MAX_PRICE_HISTORY:]
        product.current_price = price
        product.price_currency = currency
        self._changed()
        return product

    @callback
    def set_expiry(self, ean: str, expiry: date) -> ProductData:
        """Set the expiry date."""
        product = self._placeholder(ean)
        product.expiry_date = expiry.isoformat()
        product.expiry_set_at = _utcnow()
        self._changed()
        return product

    def expiring_within(self, days: int, today: date) -> list[tuple[ProductData, int]]:
        """Return (product, days left) for products expiring within days, soonest first."""
        result: list[tuple[ProductData, int]] = []
        for product in self.products.values():
            if not product.expiry_date:
                continue
            try:
                expiry = date.fromisoformat(product.expiry_date[:10])
            except ValueError:
                continue
            if (days_left := (expiry - today).days) <= days:
                result.append((product, days_left))
        return sorted(result, key=lambda item: item[1])

    def shopping_list(self) -> list[ProductData]:
        """Return products flagged as on the shopping list."""
        return [p for p in self.products.values() if p.in_shopping_list]

    @callback
    def set_in_shopping_list(self, ean: str, quantity: str | None = None) -> None:
        """Flag a product as on the shopping list."""
        if (product := self.products.get(ean)) is None:
            return
        if not product.in_shopping_list:
            product.added_to_list_at = _utcnow()
        product.in_shopping_list = True
        if quantity is not None:
            product.shopping_list_quantity = quantity
        self._changed()

    @callback
    def set_shopping_list_quantity(self, ean: str, quantity: str) -> bool:
        """Change the quantity of a listed product."""
        product = self.products.get(ean)
        if product is None or not product.in_shopping_list:
            return False
        product.shopping_list_quantity = quantity
        self._changed()
        return True

    @callback
    def clear_shopping_list_flags(self, eans: Iterable[str]) -> int:
        """Unflag products; returns how many changed."""
        count = 0
        for ean in eans:
            product = self.products.get(ean)
            if product and product.in_shopping_list:
                product.in_shopping_list = False
                product.shopping_list_quantity = None
                product.added_to_list_at = None
                count += 1
        if count:
            self._changed()
        return count

    def export(self) -> dict[str, Any]:
        """Return a backup of all products."""
        return {
            "version": STORAGE_VERSION,
            "minor_version": STORAGE_MINOR_VERSION,
            "exported_at": _utcnow(),
            "products": self._data_to_save()["products"],
            "statistics": dict(self.statistics),
        }

    @callback
    def import_data(self, data: dict[str, Any], merge: bool) -> int:
        """Import a backup (any layout). merge=False replaces all products."""
        if not isinstance(data, dict) or not ("products" in data or "mappings" in data):
            raise ValueError("Import data must contain 'products' (or legacy 'mappings')")
        imported = {
            ean: ProductData.from_dict(raw)
            for ean, raw in migrate_storage(data)["products"].items()
        }
        if merge:
            imported = {ean: p for ean, p in imported.items() if ean not in self.products}
            self.products.update(imported)
        else:
            self.products = imported
        for ean, product in imported.items():
            if product.is_named:
                self._resolved(ean)
        self._changed()
        return len(imported)
