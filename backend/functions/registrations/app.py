from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError
from shared.api import response
from shared.db import dynamodb, registrations_table
from shared.logging import log
from shared.validation import email


def _public(item: dict[str, Any]) -> dict[str, Any]:
    allowed = ("registration_id", "event_id", "status", "ticket_id", "created_at")
    return {key: next(iter(item[key].values())) for key in allowed if key in item}


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    raw_email = (event.get("pathParameters") or {}).get("email")
    registrant_email, error = email(raw_email)
    if error:
        return response(event, 400, error_code="INVALID_EMAIL", error_message=error)
    try:
        result = dynamodb().query(
            TableName=registrations_table(),
            IndexName="EmailIndex",
            KeyConditionExpression="email = :email",
            ExpressionAttributeValues={":email": {"S": registrant_email}},
            ProjectionExpression="registration_id, event_id, #s, ticket_id, created_at",
            ExpressionAttributeNames={"#s": "status"},
        )
        registrations = [_public(item) for item in result.get("Items", [])]
        log("registrations.lookup", event, count=len(registrations), status="OK")
        return response(event, 200, data={"registrations": registrations})
    except ClientError:
        log("registrations.failed", event, status="ERROR")
        return response(
            event, 503, error_code="SERVICE_UNAVAILABLE", error_message="Please try again shortly."
        )
