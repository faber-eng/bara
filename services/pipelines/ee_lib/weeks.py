import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEEK_LABEL = re.compile(r"^(\d{4})-W(\d{2})$")
ONE_DAY = timedelta(days=1)
DAYS_PER_WEEK = 7


class InvalidWeek(ValueError):
    pass


class FutureWeek(ValueError):
    pass


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


@dataclass(frozen=True)
class DryingWindow:
    s1_recent: DateRange
    s1_previous: DateRange
    rain: DateRange


def iso_week(label: object) -> date:
    match = WEEK_LABEL.match(label) if isinstance(label, str) else None
    if match is None:
        raise InvalidWeek(f"week {label!r} is not an ISO week like 2026-W42")
    year, week = (int(part) for part in match.groups())
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as error:
        raise InvalidWeek(f"week {label!r} does not exist") from error


def week_label(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def local_today(now: datetime, zone: ZoneInfo) -> date:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(zone).date()


def current_week(now: datetime, zone: ZoneInfo) -> str:
    return week_label(local_today(now, zone))


def resolve_week(label: str | None, now: datetime, zone: ZoneInfo) -> date:
    current = iso_week(current_week(now, zone))
    if label is None:
        return current
    week_start = iso_week(label)
    if week_start > current:
        raise FutureWeek(f"week {label} has not started in {zone.key}")
    return week_start


def window_end(week_start: date, today: date) -> date:
    return min(week_start + timedelta(days=DAYS_PER_WEEK), today + ONE_DAY)


def rain_end(end: date, chirps_last: date) -> date:
    return min(end, chirps_last + ONE_DAY)


def range_before(end: date, days: int) -> DateRange:
    return DateRange(end - timedelta(days=days), end)


def drying_window(
    week_start: date, *, today: date, chirps_last: date, s1_days: int, rain_days: int
) -> DryingWindow:
    end = window_end(week_start, today)
    recent = range_before(end, s1_days)
    return DryingWindow(
        s1_recent=recent,
        s1_previous=range_before(recent.start, s1_days),
        rain=range_before(rain_end(end, chirps_last), rain_days),
    )


def same_day_in_year(day: date, year: int) -> date:
    if day.month == 2 and day.day == 29:
        return date(year, 2, 28)
    return day.replace(year=year)
