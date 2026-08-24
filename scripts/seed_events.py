"""Explicit, repeatable sample-data seeder; never runs automatically during deployment."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--file", default="events/sample-events.json")
    args = parser.parse_args()
    table = boto3.resource("dynamodb").Table(args.table)
    now = datetime.now(UTC).isoformat()
    for event in json.loads(Path(args.file).read_text(encoding="utf-8")):
        table.put_item(Item={**event, "created_at": now, "updated_at": now}, ConditionExpression="attribute_not_exists(event_id)")
        print(f"seeded {event['event_id']}")


if __name__ == "__main__":
    main()
