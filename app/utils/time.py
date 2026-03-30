from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_ted_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(cleaned.replace("Z", "+00:00")))
    except ValueError:
        parsed_date = date.fromisoformat(cleaned)
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)


def parse_ted_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
    except ValueError:
        return date.fromisoformat(cleaned)


def to_timezone(value: datetime | None, timezone_name: str) -> datetime | None:
    if value is None:
        return None
    return ensure_utc(value).astimezone(ZoneInfo(timezone_name))


def format_datetime(value: datetime | None, timezone_name: str) -> str:
    localized = to_timezone(value, timezone_name)
    if localized is None:
        return "Unknown"
    return localized.strftime("%Y-%m-%d %H:%M %Z")


def format_date(value: date | None) -> str:
    return value.isoformat() if value else "Unknown"

