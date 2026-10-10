"""Audit-period constants and date helpers (business days, AD FILETIME)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

# Fiscal year under audit (fictional company, FY ends 30 September).
PERIOD_START = date(2025, 10, 1)
PERIOD_END = date(2026, 9, 30)
FISCAL_YEAR = "FY2026"

# AD stores timestamps as 100-ns intervals since 1601-01-01 UTC ("FILETIME").
_EPOCH_1601 = datetime(1601, 1, 1, tzinfo=UTC)
NEVER = 0x7FFFFFFFFFFFFFFF


def to_filetime(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int((dt - _EPOCH_1601).total_seconds() * 10_000_000)


def from_filetime(value: int | str | None) -> datetime | None:
    """Convert an AD FILETIME to an aware datetime. 0 and 'never' map to None."""
    if value in (None, "", 0, "0"):
        return None
    v = int(value)
    if v <= 0 or v >= NEVER:
        return None
    return _EPOCH_1601 + timedelta(microseconds=v // 10)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def add_business_days(d: date, n: int) -> date:
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    cur = d
    while remaining:
        cur += timedelta(days=step)
        if is_business_day(cur):
            remaining -= 1
    return cur


def business_days_between(start: date, end: date) -> int:
    """Business days elapsed from start to end (0 if same day; negative if end < start).

    Weekends are excluded; public holidays are not modelled (stated limitation).
    """
    if end == start:
        return 0
    sign = 1 if end > start else -1
    lo, hi = (start, end) if sign == 1 else (end, start)
    count = 0
    cur = lo
    while cur < hi:
        cur += timedelta(days=1)
        if is_business_day(cur):
            count += 1
    return sign * count


def parse_date(value: str | date | datetime | None) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_dt(value: str | datetime | None) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
