"""Unit tests for datetime normalization and safe comparison utilities."""

from datetime import datetime, timezone, timedelta
from app.core.datetime_utils import to_utc_naive, safe_datetime_gt, safe_datetime_le, safe_sort_key


def test_to_utc_naive_conversion():
    # Offset-aware in +05:30
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    dt_aware = datetime(2026, 11, 17, 15, 30, 0, tzinfo=tz_ist)
    dt_naive = to_utc_naive(dt_aware)
    assert dt_naive.tzinfo is None
    assert dt_naive == datetime(2026, 11, 17, 10, 0, 0)

    # Offset-aware in UTC
    dt_utc_aware = datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)
    dt_naive_from_utc = to_utc_naive(dt_utc_aware)
    assert dt_naive_from_utc.tzinfo is None
    assert dt_naive_from_utc == datetime(2026, 11, 17, 10, 0, 0)

    # Already naive
    dt_naive_input = datetime(2026, 11, 17, 10, 0, 0)
    assert to_utc_naive(dt_naive_input) == dt_naive_input

    # None
    assert to_utc_naive(None) is None


def test_safe_datetime_comparisons():
    # Comparing aware vs naive
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    dt_aware_early = datetime(2026, 11, 17, 14, 0, 0, tzinfo=tz_ist)  # 08:30 UTC
    dt_naive_late = datetime(2026, 11, 17, 9, 30, 0)                  # 09:30 UTC

    # dt_naive_late (09:30 UTC) > dt_aware_early (08:30 UTC)
    assert safe_datetime_gt(dt_naive_late, dt_aware_early) is True
    assert safe_datetime_gt(dt_aware_early, dt_naive_late) is False

    # safe_datetime_le
    assert safe_datetime_le(dt_aware_early, dt_naive_late) is True
    assert safe_datetime_le(dt_naive_late, dt_aware_early) is False

    # None handling
    assert safe_datetime_gt(dt_naive_late, None) is True
    assert safe_datetime_gt(None, dt_naive_late) is False
    assert safe_datetime_le(None, dt_naive_late) is True
    assert safe_datetime_le(dt_naive_late, None) is False


def test_safe_sort_key():
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    items = [
        datetime(2026, 11, 17, 15, 30, 0, tzinfo=tz_ist), # 10:00 UTC
        None,
        datetime(2026, 11, 17, 8, 0, 0),                  # 08:00 UTC
        datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc), # 12:00 UTC
    ]
    sorted_items = sorted(items, key=safe_sort_key)
    assert sorted_items[0] is None
    assert sorted_items[1] == datetime(2026, 11, 17, 8, 0, 0)
    assert sorted_items[2] == datetime(2026, 11, 17, 15, 30, 0, tzinfo=tz_ist)
    assert sorted_items[3] == datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
