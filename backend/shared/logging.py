from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log(operation: str, event: dict[str, Any], **fields: Any) -> None:
    """Emit JSON logs; callers must use identifiers, never raw PII."""
    request_id = (event.get("requestContext") or {}).get("requestId")
    logger.info(
        json.dumps({"operation": operation, "request_id": request_id, **fields}, default=str)
    )


def timer() -> float:
    return time.perf_counter()
