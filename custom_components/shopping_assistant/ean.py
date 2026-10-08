"""Barcode (GTIN/EAN/UPC) helpers."""
from __future__ import annotations

import re
from typing import Any

GTIN_LENGTHS = frozenset({8, 12, 13, 14})

_DIGIT_RUN_RE = re.compile(r"(?<!\d)\d{8,14}(?!\d)")
_SEPARATORS_RE = re.compile(r"[\s-]")


def gtin_checksum_valid(code: str) -> bool:
    """Return True if code is a GTIN-8/12/13/14 with a correct check digit."""
    if not code.isdigit() or len(code) not in GTIN_LENGTHS:
        return False
    *body, check = (int(char) for char in code)
    total = sum(
        digit * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    return (10 - total % 10) % 10 == check


def normalize_ean(code: str) -> str:
    """Return the canonical key for a barcode.

    A 12-digit UPC-A and a zero-padded GTIN-14 identify the same product as
    the 13-digit EAN, which is how OpenFoodFacts stores them.
    """
    if len(code) == 12:
        return f"0{code}"
    if len(code) == 14 and code.startswith("0"):
        return code[1:]
    return code


def extract_ean(text: Any) -> str | None:
    """Find the first valid GTIN in free text, such as a shared message or URL.

    Only standalone digit runs with a valid check digit count, so dates,
    phone numbers and IDs inside URLs are not mistaken for barcodes.
    """
    for match in _DIGIT_RUN_RE.finditer(str(text or "")):
        if gtin_checksum_valid(code := match.group()):
            return normalize_ean(code)
    return None


def parse_ean(value: Any) -> str:
    """Validate a barcode typed by the user and return its canonical key.

    Spaces and dashes are ignored. Any 8-14 digit code is accepted so store
    specific codes can still be mapped; scans use extract_ean instead.
    """
    code = _SEPARATORS_RE.sub("", str(value or ""))
    if not code.isdigit() or not 8 <= len(code) <= 14:
        raise ValueError(f"Invalid EAN: {value!r} (expected 8-14 digits)")
    return normalize_ean(code)
