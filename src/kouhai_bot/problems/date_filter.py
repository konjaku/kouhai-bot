"""Contest-date parsing shared by configuration and the picker."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone


TZ = timezone(timedelta(hours=8))
_YEAR_RE = re.compile(r"\d{4}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def normalize_contest_date_bound(value: object, *, upper: bool) -> str:
    """Normalize YYYY or YYYY-MM-DD to an inclusive ISO date boundary."""
    text = str(value or "").strip()
    if not text:
        return ""
    if _YEAR_RE.fullmatch(text):
        year = int(text)
        return date(year, 12 if upper else 1, 31 if upper else 1).isoformat()
    if not _DATE_RE.fullmatch(text):
        raise ValueError("expected YYYY or YYYY-MM-DD")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid calendar date: {text}") from exc


def normalize_contest_date_range(
    minimum: object,
    maximum: object,
) -> tuple[str, str]:
    """Return canonical inclusive date bounds and reject reversed ranges."""
    min_date = normalize_contest_date_bound(minimum, upper=False)
    max_date = normalize_contest_date_bound(maximum, upper=True)
    if min_date and max_date and min_date > max_date:
        raise ValueError("min_contest_date must not be after max_contest_date")
    return min_date, max_date


def contest_date_from_timestamp(timestamp: object) -> str:
    """Convert a Codeforces unix start time to its Asia/Shanghai date."""
    return datetime.fromtimestamp(int(timestamp), tz=TZ).date().isoformat()


def contest_timestamp_in_range(
    timestamp: object,
    minimum: str,
    maximum: str,
) -> bool:
    """Return whether a contest timestamp lies inside inclusive date bounds."""
    contest_date = contest_date_from_timestamp(timestamp)
    return (not minimum or contest_date >= minimum) and (
        not maximum or contest_date <= maximum
    )
