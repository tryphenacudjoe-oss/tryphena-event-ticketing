import os

os.environ.update(
    {
        "EVENTS_TABLE": "events",
        "REGISTRATIONS_TABLE": "registrations",
        "ALLOWED_ORIGINS": "http://localhost:5173",
    }
)
