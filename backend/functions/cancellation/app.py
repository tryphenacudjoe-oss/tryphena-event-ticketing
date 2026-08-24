from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError
from shared.api import response
from shared.db import dynamodb, events_table, registrations_table
from shared.logging import log
from shared.validation import identifier


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    registration_id, error = identifier(
        (event.get("pathParameters") or {}).get("id"), "Registration ID"
    )
    if error:
        return response(event, 400, error_code="INVALID_REGISTRATION_ID", error_message=error)
    db = dynamodb()
    try:
        record = db.get_item(
            TableName=registrations_table(),
            Key={"registration_id": {"S": registration_id}},
            ConsistentRead=True,
        ).get("Item")
    except ClientError:
        return response(
            event, 503, error_code="SERVICE_UNAVAILABLE", error_message="Please try again shortly."
        )
    if not record:
        return response(
            event,
            404,
            error_code="REGISTRATION_NOT_FOUND",
            error_message="Registration was not found.",
        )
    if record["status"]["S"] == "CANCELLED":
        return response(
            event,
            200,
            data={"registration_id": registration_id, "status": "CANCELLED"},
            message="Registration was already cancelled",
        )
    now = datetime.now(UTC).isoformat()
    try:
        db.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": registrations_table(),
                        "Key": {"registration_id": {"S": registration_id}},
                        "UpdateExpression": "SET #s = :cancelled, updated_at = :now",
                        "ConditionExpression": "#s = :active",
                        "ExpressionAttributeNames": {"#s": "status"},
                        "ExpressionAttributeValues": {
                            ":active": {"S": "ACTIVE"},
                            ":cancelled": {"S": "CANCELLED"},
                            ":now": {"S": now},
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": events_table(),
                        "Key": {"event_id": record["event_id"]},
                        "UpdateExpression": "SET available_seats = available_seats + :one, updated_at = :now",
                        "ConditionExpression": "attribute_exists(event_id) AND available_seats < capacity",
                        "ExpressionAttributeValues": {":one": {"N": "1"}, ":now": {"S": now}},
                    }
                },
            ]
        )
    except ClientError as exc:
        log(
            "cancellation.failed",
            event,
            registration_id=registration_id,
            reason=exc.response.get("Error", {}).get("Code"),
        )
        return response(
            event,
            409,
            error_code="CANCELLATION_CONFLICT",
            error_message="This registration could not be cancelled. Please refresh and try again.",
        )
    log("cancellation.succeeded", event, registration_id=registration_id, status="CANCELLED")
    return response(
        event,
        200,
        data={"registration_id": registration_id, "status": "CANCELLED"},
        message="Registration cancelled",
    )
