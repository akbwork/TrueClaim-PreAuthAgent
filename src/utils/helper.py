import re
from datetime import datetime, timezone
from typing import Any

def normalize(value: str | None) -> str:
    """Lowercase, strip spaces and special chars for fuzzy comparison."""
    if not value:
        return ""
    return re.sub(r"[\s\-_]+", " ", value.strip().lower())

def _parse_dt(value: Any) -> datetime | None:
    """Parse a datetime string or object into a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

