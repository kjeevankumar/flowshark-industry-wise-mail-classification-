"""Datetime utilities for timezone normalization and safe comparisons.

Provides robust conversion to UTC naive datetimes to prevent
'can't compare offset-naive and offset-aware datetimes' errors
when interacting with databases (SQLite/PostgreSQL) and parsed email headers.
"""

from datetime import datetime, timezone
from typing import Optional


def to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert any datetime (aware or naive) to UTC offset-naive datetime.

    If dt is None, returns None.
    If dt has tzinfo, converts to UTC and drops tzinfo.
    If dt is naive, returns as-is.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def safe_datetime_gt(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    """Safely check if dt1 > dt2 even when mixing offset-aware and offset-naive datetimes."""
    if dt1 is None:
        return False
    if dt2 is None:
        return True
    d1 = to_utc_naive(dt1)
    d2 = to_utc_naive(dt2)
    return d1 > d2


def safe_datetime_le(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    """Safely check if dt1 <= dt2 even when mixing offset-aware and offset-naive datetimes."""
    if dt1 is None:
        return True
    if dt2 is None:
        return False
    d1 = to_utc_naive(dt1)
    d2 = to_utc_naive(dt2)
    return d1 <= d2


def safe_sort_key(dt: Optional[datetime]) -> datetime:
    """Safe key for sorting datetimes that may be mixed aware/naive or None."""
    if dt is None:
        return datetime.min
    return to_utc_naive(dt) or datetime.min
