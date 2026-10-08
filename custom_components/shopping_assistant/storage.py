"""Storage format of Shopping Assistant.

Everything is one document in .storage/shopping_assistant:

    {
      "products":       {"<barcode>": Product, ...},
      "unknowns":       {"<barcode>": UnknownProduct, ...},
      "shopping_list":  [ListItem, ...],
      "statistics":     {"total_scans": 0, ...},
      "last_missing_ean": "<barcode>" or null
    }

Rules that keep the format stable:

- Every record is a flat JSON object. Adding a field needs no migration:
  older data simply lacks it and the field's default applies.
- Fields and sections this version does not know are kept and written back,
  so data from a newer version survives a downgrade.
- Renaming, moving or reshaping data needs a migration step in MIGRATIONS
  and a STORAGE_MINOR_VERSION bump (STORAGE_VERSION for breaking changes).
  Steps run in order on load and on import of an older export.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar, Self

from homeassistant.helpers.storage import Store

from .const import STORAGE_MINOR_VERSION, STORAGE_VERSION

type Data = dict[str, Any]

# Migration steps keyed by the (version, minor version) they upgrade from.
MIGRATIONS: dict[tuple[int, int], Callable[[Data], Data]] = {}


def migrate(data: Data, version: int, minor_version: int) -> Data:
    """Upgrade data written by an older version to the current format."""
    for step_version, step in sorted(MIGRATIONS.items()):
        if step_version >= (version, minor_version):
            data = step(data)
    return data


class VersionedStore(Store[Data]):
    """Store that runs the migration steps on load."""

    def __init__(self, hass: Any, key: str) -> None:
        """Initialize."""
        super().__init__(hass, STORAGE_VERSION, key, minor_version=STORAGE_MINOR_VERSION)

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: Data
    ) -> Data:
        return migrate(old_data, old_major_version, old_minor_version)


@dataclass(slots=True)
class Record:
    """Base for stored records: tolerant loading, compact saving.

    Keys without a field go to ``extra`` and are saved again unchanged.
    """

    extra: Data = field(default_factory=dict, kw_only=True)

    # Keys whose empty values are still saved.
    KEEP_EMPTY: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def from_dict(cls, data: Data) -> Self:
        """Build from stored data."""
        known = {item.name for item in fields(cls)} - {"extra"}
        values = {key: value for key, value in data.items() if key in known}
        extra = {key: value for key, value in data.items() if key not in known}
        return cls(**values, extra=extra)

    def to_dict(self) -> Data:
        """Serialize, leaving out empty values."""
        values = asdict(self)
        extra = values.pop("extra")
        return extra | {
            key: value
            for key, value in values.items()
            if key in self.KEEP_EMPTY or value not in (None, "", [], {})
        }
