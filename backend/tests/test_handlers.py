import json
from unittest.mock import patch

from botocore.exceptions import ClientError
from functions.cancellation.app import lambda_handler as cancel
from functions.events.app import lambda_handler as events
from functions.register.app import lambda_handler as register
from functions.registrations.app import lambda_handler as registrations


def event(body="{}", path=None):
    return {
        "body": body,
        "pathParameters": path or {},
        "headers": {"Origin": "http://localhost:5173"},
        "requestContext": {"requestId": "test"},
    }


def body(result):
    return json.loads(result["body"])


def error(code="InternalServerError", reasons=None):
    payload = {"Error": {"Code": code, "Message": "test"}}
    if reasons is not None:
        payload["CancellationReasons"] = reasons
    return ClientError(payload, "operation")


VALID = json.dumps(
    {"event_id": "workshop-2026", "name": "Ada Lovelace", "email": "ada@example.com"}
)


@patch("functions.register.app.dynamodb")
def test_register_success(mock_db):
    result = register(event(VALID), None)
    assert result["statusCode"] == 201
    assert body(result)["data"]["status"] == "ACTIVE"
    assert mock_db.return_value.transact_write_items.called
    transaction = mock_db.return_value.transact_write_items.call_args.kwargs["TransactItems"]
    assert "available_seats > :zero" in transaction[0]["Update"]["ConditionExpression"]
    assert "attribute_not_exists(registration_id)" in transaction[1]["Put"]["ConditionExpression"]


def test_register_rejects_malformed_and_bad_email():
    assert body(register(event("{"), None))["error"]["code"] == "INVALID_REQUEST"
    payload = json.dumps({"event_id": "workshop-2026", "name": "Ada", "email": "not-email"})
    assert body(register(event(payload), None))["error"]["code"] == "INVALID_EMAIL"


@patch("functions.register.app.dynamodb")
def test_register_duplicate(mock_db):
    mock_db.return_value.transact_write_items.side_effect = error(
        "TransactionCanceledException", [{}, {"Code": "ConditionalCheckFailed"}]
    )
    result = register(event(VALID), None)
    assert result["statusCode"] == 409
    assert body(result)["error"]["code"] == "DUPLICATE_REGISTRATION"


@patch("functions.register.app.dynamodb")
def test_register_full_or_unknown_event(mock_db):
    mock_db.return_value.transact_write_items.side_effect = error(
        "TransactionCanceledException", [{"Code": "ConditionalCheckFailed"}, {}]
    )
    result = register(event(VALID), None)
    assert result["statusCode"] == 409
    assert body(result)["error"]["code"] == "EVENT_UNAVAILABLE"


@patch("functions.register.app.dynamodb")
def test_register_database_failure(mock_db):
    mock_db.return_value.transact_write_items.side_effect = error()
    assert register(event(VALID), None)["statusCode"] == 503


@patch("functions.events.app.dynamodb")
def test_events_only_returns_public_shape(mock_db):
    mock_db.return_value.scan.return_value = {
        "Items": [
            {
                "event_id": {"S": "event-1"},
                "name": {"S": "Event"},
                "date": {"S": "2026-12-01"},
                "internal": {"S": "hidden"},
            }
        ]
    }
    result = events(event(), None)
    assert result["statusCode"] == 200
    assert "#c" in mock_db.return_value.scan.call_args.kwargs["ProjectionExpression"]
    assert mock_db.return_value.scan.call_args.kwargs["ExpressionAttributeNames"]["#c"] == "capacity"
    assert body(result)["data"]["events"] == [
        {"event_id": "event-1", "name": "Event", "date": "2026-12-01"}
    ]


@patch("functions.events.app.dynamodb")
def test_events_database_error(mock_db):
    mock_db.return_value.scan.side_effect = error()
    assert events(event(), None)["statusCode"] == 503


def test_lookup_validates_email():
    result = registrations(event(path={"email": "invalid"}), None)
    assert result["statusCode"] == 400


@patch("functions.registrations.app.dynamodb")
def test_lookup_returns_no_pii(mock_db):
    mock_db.return_value.query.return_value = {
        "Items": [
            {
                "registration_id": {"S": "abc"},
                "event_id": {"S": "event"},
                "status": {"S": "ACTIVE"},
                "ticket_id": {"S": "TKT"},
                "created_at": {"S": "now"},
                "email": {"S": "secret@example.com"},
            }
        ]
    }
    result = registrations(event(path={"email": "ada@example.com"}), None)
    assert result["statusCode"] == 200
    assert "email" not in body(result)["data"]["registrations"][0]


def active_record():
    return {
        "registration_id": {"S": "registration-123"},
        "event_id": {"S": "event-1"},
        "status": {"S": "ACTIVE"},
    }


@patch("functions.cancellation.app.dynamodb")
def test_cancel_success(mock_db):
    mock_db.return_value.get_item.return_value = {"Item": active_record()}
    result = cancel(event(path={"id": "registration-123"}), None)
    assert result["statusCode"] == 200
    assert mock_db.return_value.transact_write_items.called


@patch("functions.cancellation.app.dynamodb")
def test_cancel_unknown_and_idempotent(mock_db):
    mock_db.return_value.get_item.return_value = {}
    assert cancel(event(path={"id": "registration-123"}), None)["statusCode"] == 404
    item = active_record()
    item["status"] = {"S": "CANCELLED"}
    mock_db.return_value.get_item.return_value = {"Item": item}
    result = cancel(event(path={"id": "registration-123"}), None)
    assert result["statusCode"] == 200
    assert not mock_db.return_value.transact_write_items.called


@patch("functions.cancellation.app.dynamodb")
def test_cancel_race_conflict(mock_db):
    mock_db.return_value.get_item.return_value = {"Item": active_record()}
    mock_db.return_value.transact_write_items.side_effect = error("TransactionCanceledException")
    assert cancel(event(path={"id": "registration-123"}), None)["statusCode"] == 409
