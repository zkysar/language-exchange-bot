from datetime import date, datetime
from zoneinfo import ZoneInfo

LA_TZ = ZoneInfo("America/Los_Angeles")


def today_la() -> date:
    return datetime.now(LA_TZ).date()


def now_la() -> datetime:
    return datetime.now(LA_TZ)


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def format_display(d: date) -> str:
    return d.strftime("%a, %b %d, %Y")


def is_future(d: date) -> bool:
    return d >= today_la()
