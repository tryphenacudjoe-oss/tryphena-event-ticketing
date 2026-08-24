"""Consistent, privacy-conscious HTTP API responses."""

from __future__ import annotations

import json
import os
from typing import Any


def _origin(event: dict[str, Any]) -> str:
    allowed = {item.strip() for item in os.getenv("ALLOWED_ORIGINS", "").split(",") if item.strip()}
    origin = (event.get("headers") or {}).get("origin") or (event.get("headers") or {}).get(
        "Origin"
    )
    return origin if origin in allowed else ""


def response(
    event: dict[str, Any],
    status_code: int,
    *,
    data: Any = None,
    message: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any]
    if status_code < 400:
        body = {"success": True, "data": data if data is not None else {}}
        if message:
            body["message"] = message
    else:
        body = {
            "success": False,
            "error": {
                "code": error_code or "INTERNAL_ERROR",
                "message": error_message or "An unexpected error occurred.",
            },
        }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    origin = _origin(event)
    if origin:
        headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Headers": "Content-Type,X-Request-Id",
                "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
            }
        )
    return {"statusCode": status_code, "headers": headers, "body": json.dumps(body, default=str)}


def parse_json_body(event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw = event.get("body") or ""
    if len(raw.encode("utf-8")) > 8_192:
        return None, "Request body must not exceed 8 KB."
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None, "Request body must be valid JSON."
    if not isinstance(value, dict):
        return None, "Request body must be an object."
    return value, None
