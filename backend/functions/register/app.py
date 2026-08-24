"""Concurrency-safe event registration handler."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError
from shared.api import parse_json_body, response
from shared.db import dynamodb, events_table, registrations_table
from shared.logging import log
from shared.validation import clean_text, email, identifier


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    body, parse_error = parse_json_body(event)
    if parse_error:
        return response(event, 400, error_code="INVALID_REQUEST", error_message=parse_error)
    assert body is not None
    event_id, error = identifier(body.get("event_id"), "Event ID")
    if error:
        return response(event, 400, error_code="INVALID_EVENT_ID", error_message=error)
    registrant_name, error = clean_text(body.get("name"), "Name")
    if error:
        return response(event, 400, error_code="INVALID_NAME", error_message=error)
    registrant_email, error = email(body.get("email"))
    if error:
        return response(event, 400, error_code="INVALID_EMAIL", error_message=error)

    # Deterministic ID makes duplicate registrations for an event/email impossible without a GSI race.
    registration_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"event-ticketing:{event_id}:{registrant_email}")
    )
    ticket_id = f"TKT-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(UTC).isoformat()
    db = dynamodb()
    try:
        db.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": events_table(),
                        "Key": {"event_id": {"S": event_id}},
                        "UpdateExpression": "SET available_seats = available_seats - :one, updated_at = :now",
                        "ConditionExpression": "attribute_exists(event_id) AND #status = :open AND available_seats > :zero",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":one": {"N": "1"},
                            ":zero": {"N": "0"},
                            ":open": {"S": "OPEN"},
                            ":now": {"S": now},
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": registrations_table(),
                        "Item": {
                            "registration_id": {"S": registration_id},
                            "event_id": {"S": event_id},
                            "email": {"S": registrant_email},
                            "name": {"S": registrant_name},
                            "status": {"S": "ACTIVE"},
                            "ticket_id": {"S": ticket_id},
                            "created_at": {"S": now},
                            "updated_at": {"S": now},
                            "email_created": {"S": f"{registrant_email}#{now}"},
                        },
                        "ConditionExpression": "attribute_not_exists(registration_id)",
                    }
                },
            ]
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        reasons = exc.response.get("CancellationReasons", [])
        log("register.failed", event, event_id=event_id, reason=code)
        if code == "TransactionCanceledException":
            if len(reasons) > 1 and reasons[1].get("Code") == "ConditionalCheckFailed":
                return response(
                    event,
                    409,
                    error_code="DUPLICATE_REGISTRATION",
                    error_message="You are already registered for this event.",
                )
            return response(
                event,
                409,
                error_code="EVENT_UNAVAILABLE",
                error_message="This event is full, closed, or unavailable.",
            )
        return response(
            event, 503, error_code="SERVICE_UNAVAILABLE", error_message="Please try again shortly."
        )
    log(
        "register.succeeded",
        event,
        event_id=event_id,
        registration_id=registration_id,
        status="ACTIVE",
    )
    return response(
        event,
        201,
        data={
            "registration_id": registration_id,
            "ticket_id": ticket_id,
            "event_id": event_id,
            "status": "ACTIVE",
        },
        message="Registration successful",
    )
