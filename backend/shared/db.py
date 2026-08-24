from __future__ import annotations

import os

import boto3


def dynamodb():
    return boto3.client("dynamodb")


def events_table() -> str:
    return os.environ["EVENTS_TABLE"]


def registrations_table() -> str:
    return os.environ["REGISTRATIONS_TABLE"]
