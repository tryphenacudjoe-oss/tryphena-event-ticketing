from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,63}$", re.IGNORECASE)
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,79}$")


def clean_text(
    value: Any, field: str, minimum: int = 2, maximum: int = 120
) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, f"{field} is required."
    cleaned = " ".join(value.strip().split())
    if not minimum <= len(cleaned) <= maximum or any(ord(char) < 32 for char in cleaned):
        return None, f"{field} must be between {minimum} and {maximum} characters."
    return cleaned, None


def email(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "A valid email address is required."
    cleaned = value.strip().lower()
    if len(cleaned) > 254 or not EMAIL_RE.fullmatch(cleaned):
        return None, "A valid email address is required."
    return cleaned, None


def identifier(value: Any, label: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        return None, f"{label} is invalid."
    return value, None
