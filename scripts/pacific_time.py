#!/usr/bin/env python3
"""
US Pacific Timezone (`America/Los_Angeles`) Utility (`pacific_time.py`).

Automatically resolves to Pacific Standard Time (`PST`, `UTC-08:00`) during Standard Time
and Pacific Daylight Time (`PDT`, `UTC-07:00`) during Daylight Saving Time using the
US Energy Policy Act of 2005 DST rule (2nd Sunday in March at 02:00 PST to 1st Sunday in
November at 02:00 PDT).
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, Union


def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    first_day = dt.date(year, month, 1)
    days_until_sunday = (6 - first_day.weekday()) % 7
    return first_day + dt.timedelta(days=days_until_sunday + 7 * (n - 1))


def _is_us_pacific_dst_local(naive_local: dt.datetime) -> bool:
    year = naive_local.year
    dst_start = dt.datetime.combine(_nth_sunday(year, 3, 2), dt.time(2, 0, 0))
    dst_end = dt.datetime.combine(_nth_sunday(year, 11, 1), dt.time(2, 0, 0))
    return dst_start <= naive_local < dst_end


class USPacificTz(dt.tzinfo):
    _STD_OFFSET = dt.timedelta(hours=-8)
    _DST_OFFSET = dt.timedelta(hours=-7)
    _DST_DIFF = dt.timedelta(hours=1)
    _ZERO = dt.timedelta(0)

    def utcoffset(self, d: Optional[dt.datetime]) -> dt.timedelta:
        if d is None:
            return self._DST_OFFSET if self._current_is_dst() else self._STD_OFFSET
        return self._DST_OFFSET if _is_us_pacific_dst_local(d.replace(tzinfo=None)) else self._STD_OFFSET

    def dst(self, d: Optional[dt.datetime]) -> dt.timedelta:
        if d is None:
            return self._DST_DIFF if self._current_is_dst() else self._ZERO
        return self._DST_DIFF if _is_us_pacific_dst_local(d.replace(tzinfo=None)) else self._ZERO

    def tzname(self, d: Optional[dt.datetime]) -> str:
        if d is None:
            return "PDT" if self._current_is_dst() else "PST"
        return "PDT" if _is_us_pacific_dst_local(d.replace(tzinfo=None)) else "PST"

    def fromutc(self, d: dt.datetime) -> dt.datetime:
        if d.tzinfo is not self:
            raise ValueError("fromutc: dt.tzinfo is not self")
        naive_utc = d.replace(tzinfo=None)
        year = naive_utc.year
        dst_start_utc = dt.datetime.combine(_nth_sunday(year, 3, 2), dt.time(10, 0, 0))
        dst_end_utc = dt.datetime.combine(_nth_sunday(year, 11, 1), dt.time(9, 0, 0))
        if dst_start_utc <= naive_utc < dst_end_utc:
            return (naive_utc + self._DST_OFFSET).replace(tzinfo=self)
        return (naive_utc + self._STD_OFFSET).replace(tzinfo=self)

    @classmethod
    def _current_is_dst(cls) -> bool:
        now_utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        year = now_utc.year
        dst_start_utc = dt.datetime.combine(_nth_sunday(year, 3, 2), dt.time(10, 0, 0))
        dst_end_utc = dt.datetime.combine(_nth_sunday(year, 11, 1), dt.time(9, 0, 0))
        return dst_start_utc <= now_utc < dst_end_utc


PACIFIC_TZ = USPacificTz()


def now_pacific() -> dt.datetime:
    return dt.datetime.now(tz=PACIFIC_TZ)


def to_pacific(val: Union[dt.datetime, dt.date, str, int, float, None]) -> Optional[dt.datetime]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return dt.datetime.fromtimestamp(float(val), tz=PACIFIC_TZ)
    if isinstance(val, dt.datetime):
        return val.replace(tzinfo=PACIFIC_TZ) if val.tzinfo is None else val.astimezone(PACIFIC_TZ)
    if isinstance(val, dt.date):
        return dt.datetime(val.year, val.month, val.day, 0, 0, 0, tzinfo=PACIFIC_TZ)
    if isinstance(val, str):
        clean = val.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(clean)
            return parsed.replace(tzinfo=PACIFIC_TZ) if parsed.tzinfo is None else parsed.astimezone(PACIFIC_TZ)
        except Exception:
            return None
    return None


def format_pacific(val: Union[dt.datetime, dt.date, str, int, float, None] = None, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    target = now_pacific() if val is None else to_pacific(val)
    return target.strftime(fmt) if target else str(val or "N/A")
