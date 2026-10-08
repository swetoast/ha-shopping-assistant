"""Local product database for Shopping Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
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
from .shopping import ShoppingList
from .storage import Data, Record, VersionedStore, migrate

SOURCE_OFF = "openfoodfacts"
SOURCE_OFF_EDITED = "openfoodfacts+manual"
SOURCE_MANUAL = "manual"
SOURCE_LOCAL = "local"  # placeholder created by price/expiry tracking


def _utcnow() -> str:
    """Return the current UTC time as an ISO string."""
    return dt_util.utcnow().isoformat()


@dataclass(slots=True)
class ProductData(Record):
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
    last_scanned: str | None = None
    prices: list[dict[str, Any]] = field(default_factory=list)
    current_price: float | None = None
    price_currency: str | None = None
    expiry_date: str | None = None
    expiry_set_at: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: Data) -> ProductData:
        """Build from stored data."""
        return super(ProductData, cls).from_dict(
            {"product_name": UNKNOWN_PRODUCT_NAME, "source": SOURCE_MANUAL} | data
        )

    @property
    def last_activity(self) -> str:
        """Return when the product was last scanned or changed."""
        return max(self.first_seen, self.last_updated, self.last_scanned or "")

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
    "last_scanned",
    "prices",
    "current_price",
    "price_currency",
    "expiry_date",
    "expiry_set_at",
    "notes",
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
class UnknownProduct(Record):
    """A barcode OpenFoodFacts does not know."""

    ean: str
    first_seen: str = field(default_factory=_utcnow)
    last_seen: str = field(default_factory=_utcnow)
    seen_count: int = 1


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


SECTIONS = ("products", "unknowns", "shopping_list", "statistics", "last_missing_ean")


class ProductDatabase:
    """Products, unknown barcodes, the shopping list and statistics.

    Saved as one document; see storage.py for the format.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._store = VersionedStore(hass, STORAGE_KEY)
        self.products: dict[str, ProductData] = {}
        self.unknowns: dict[str, UnknownProduct] = {}
        self.last_missing_ean: str | None = None
        self.statistics: dict[str, Any] = _default_statistics()
        self.shopping = ShoppingList(self._changed)
        self._other: Data = {}

    async def async_load(self) -> None:
        """Load from disk."""
        self._apply(await self._store.async_load() or {})

    def _apply(self, data: Data) -> None:
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
        self.shopping.load(data.get("shopping_list") or [])
        self._other = {key: value for key, value in data.items() if key not in SECTIONS}

    def _data_to_save(self) -> Data:
        return self._other | {
            "products": {ean: p.to_dict() for ean, p in self.products.items()},
            "unknowns": {ean: u.to_dict() for ean, u in self.unknowns.items()},
            "shopping_list": self.shopping.dump(),
            "statistics": self.statistics,
            "last_missing_ean": self.last_missing_ean,
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
            product.extra = existing.extra
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
        """Delete a product, its unknown entry and its shopping list items."""
        self.shopping.remove([i for i in self.shopping.items.values() if i.ean == ean])
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
            product.last_scanned = stats["last_scan_time"]
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

    def export(self) -> Data:
        """Return everything as a backup that import_data accepts."""
        return {
            "version": STORAGE_VERSION,
            "minor_version": STORAGE_MINOR_VERSION,
            "exported_at": _utcnow(),
            **self._data_to_save(),
        }

    @callback
    def import_data(self, data: Data, merge: bool) -> int:
        """Import a backup made by export.

        merge=True only adds products that are not stored yet. merge=False
        replaces all products and, if the backup has one, the shopping list.
        Returns how many products were imported.
        """
        if not isinstance(data.get("products"), dict):
            raise ValueError("Import data must contain 'products', as made by export_data")
        data = migrate(
            data,
            int(data.get("version", STORAGE_VERSION)),
            int(data.get("minor_version", STORAGE_MINOR_VERSION)),
        )
        imported = {
            key: ProductData.from_dict({**raw, "ean": key})
            for ean, raw in data["products"].items()
            if isinstance(raw, dict) and (key := _storage_key(ean))
        }
        if merge:
            imported = {ean: p for ean, p in imported.items() if ean not in self.products}
            self.products.update(imported)
        else:
            self.products = imported
            if "shopping_list" in data:
                self.shopping.load(data["shopping_list"])
        for ean, product in imported.items():
            if product.is_named:
                self._resolved(ean)
        self._changed()
        return len(imported)

    @callback
    def reset(self, sections: set[str], before: datetime | None = None) -> Data:
        """Remove stored data and return how much was removed.

        sections picks from products, unknowns, shopping_list and statistics.
        With before, only data older than that goes: products not scanned or
        changed since then (unless on the shopping list), unknown barcodes not
        seen since then and list items added before then. Statistics are only
        reset without before.
        """
        cutoff = before.isoformat() if before else None

        def old(stamp: str | None) -> bool:
            return cutoff is None or (stamp or "") < cutoff

        removed: Data = {}
        if "shopping_list" in sections:
            removed["shopping_list"] = self.shopping.remove(
                [item for item in self.shopping.items.values() if old(item.added_at)]
            )
        if "products" in sections:
            listed = {item.ean for item in self.shopping.items.values()}
            gone = [
                ean
                for ean, product in self.products.items()
                if ean not in listed and old(product.last_activity)
            ]
            for ean in gone:
                del self.products[ean]
            removed["products"] = len(gone)
        if "unknowns" in sections:
            gone = [ean for ean, u in self.unknowns.items() if old(u.last_seen)]
            for ean in gone:
                self._resolved(ean)
            removed["unknowns"] = len(gone)
        if "statistics" in sections and cutoff is None:
            self.statistics = _default_statistics()
            removed["statistics"] = True
        self._changed()
        return removed
