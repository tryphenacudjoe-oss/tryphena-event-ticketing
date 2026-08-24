from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError
from shared.api import response
from shared.db import dynamodb, events_table
from shared.logging import log


def _event(item: dict[str, Any]) -> dict[str, Any]:
    """Whitelist public fields so schema changes cannot leak internals."""
    return {
        key: item[key]
        for key in (
            "event_id",
            "name",
            "description",
            "date",
            "location",
            "capacity",
            "available_seats",
            "status",
        )
        if key in item
    }


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        items: list[dict[str, Any]] = []
        scan_args: dict[str, Any] = {
            "TableName": events_table(),
            "ProjectionExpression": "event_id, #n, description, #d, location, capacity, available_seats, #s",
            "ExpressionAttributeNames": {"#n": "name", "#d": "date", "#s": "status"},
        }
        while True:
            result = dynamodb().scan(**scan_args)
            items.extend(
                {key: next(iter(value.values())) for key, value in row.items()}
                for row in result.get("Items", [])
            )
            last_key = result.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_args["ExclusiveStartKey"] = last_key
        items.sort(key=lambda item: item.get("date", ""))
        log("events.list", event, count=len(items), status="OK")
        return response(event, 200, data={"events": [_event(item) for item in items]})
    except ClientError:
        log("events.failed", event, status="ERROR")
        return response(
            event, 503, error_code="SERVICE_UNAVAILABLE", error_message="Please try again shortly."
        )
