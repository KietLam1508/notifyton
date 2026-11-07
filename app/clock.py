"""Thời gian hệ thống và ngày làm việc.

Cho phép đặt "ngày hệ thống" (setting `demo_today`) để demo và kiểm thử các rule theo hạn.
"""
from datetime import date, datetime, timedelta

from . import settings as S


def today(conn) -> date:
    override = S.get(conn, "demo_today")
    if override:
        return date.fromisoformat(override)
    return date.today()


def now(conn) -> str:
    """Thời điểm hiện tại (ISO, đến giây), tôn trọng ngày hệ thống demo."""
    t = datetime.now().time().replace(microsecond=0)
    return datetime.combine(today(conn), t).isoformat(sep=" ")


def to_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def holidays(conn) -> set[date]:
    raw = S.get(conn, "holidays") or ""
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            out.add(date.fromisoformat(part))
    return out


def is_business_day(conn, d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(conn)


def add_business_days(conn, start, n: int) -> date:
    d = to_date(start)
    hol = holidays(conn)
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in hol:
            added += 1
    return d


def business_days_between(conn, start, end) -> int:
    """Số ngày làm việc trôi qua sau `start` tính đến hết `end`."""
    s, e = to_date(start), to_date(end)
    hol = holidays(conn)
    count = 0
    d = s
    while d < e:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in hol:
            count += 1
    return count
