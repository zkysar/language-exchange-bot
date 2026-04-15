import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU

WEEKDAYS = {
    "monday": MO, "tuesday": TU, "wednesday": WE, "thursday": TH,
    "friday": FR, "saturday": SA, "sunday": SU,
}
ORDINALS = {
    "1st": 1, "first": 1, "2nd": 2, "second": 2, "3rd": 3, "third": 3,
    "4th": 4, "fourth": 4, "5th": 5, "fifth": 5, "last": -1,
}


@dataclass
class ParsedPattern:
    kind: str  # "nth_weekday", "monthly", "biweekly", "weekly"
    weekday: Optional[int] = None  # 0=Mon..6=Sun
    nth: Optional[int] = None  # 1..5 or -1
    day_of_month: Optional[int] = None
    description: str = ""


def parse_pattern(text: str) -> ParsedPattern:
    t = text.strip().lower()
    m = re.match(r"every\s+(\w+)\s+(\w+)", t)
    if m:
        ord_word, wd_word = m.group(1), m.group(2)
        if ord_word in ORDINALS and wd_word in WEEKDAYS:
            return ParsedPattern(
                kind="nth_weekday",
                weekday=list(WEEKDAYS.keys()).index(wd_word),
                nth=ORDINALS[ord_word],
                description=text,
            )
    m = re.match(r"every\s+(\w+)", t)
    if m and m.group(1) in WEEKDAYS:
        return ParsedPattern(
            kind="weekly",
            weekday=list(WEEKDAYS.keys()).index(m.group(1)),
            description=text,
        )
    if "biweekly" in t or "every other" in t:
        for wd in WEEKDAYS:
            if wd in t:
                return ParsedPattern(
                    kind="biweekly",
                    weekday=list(WEEKDAYS.keys()).index(wd),
                    description=text,
                )
    if t in ("monthly", "every month"):
        return ParsedPattern(kind="monthly", day_of_month=1, description=text)
    m = re.match(r"monthly\s+on\s+the\s+(\d+)", t)
    if m:
        return ParsedPattern(
            kind="monthly", day_of_month=int(m.group(1)), description=text
        )
    raise ValueError(f"Could not parse pattern: {text!r}")


def generate_dates(pattern: ParsedPattern, start: date, months: int = 3) -> List[date]:
    end = start + relativedelta(months=months)
    out: List[date] = []
    if pattern.kind == "nth_weekday":
        wd_obj = list(WEEKDAYS.values())[pattern.weekday]
        current = start.replace(day=1)
        while current <= end:
            if pattern.nth == -1:
                candidate = current + relativedelta(day=31, weekday=wd_obj(-1))
            else:
                candidate = current + relativedelta(day=1, weekday=wd_obj(pattern.nth))
            if candidate.month == current.month and start <= candidate <= end:
                out.append(candidate)
            current += relativedelta(months=1)
    elif pattern.kind == "weekly":
        current = start
        while current.weekday() != pattern.weekday:
            current += timedelta(days=1)
        while current <= end:
            out.append(current)
            current += timedelta(days=7)
    elif pattern.kind == "biweekly":
        current = start
        while current.weekday() != pattern.weekday:
            current += timedelta(days=1)
        while current <= end:
            out.append(current)
            current += timedelta(days=14)
    elif pattern.kind == "monthly":
        current = start.replace(day=1)
        while current <= end:
            try:
                candidate = current.replace(day=pattern.day_of_month)
                if start <= candidate <= end:
                    out.append(candidate)
            except ValueError:
                pass
            current += relativedelta(months=1)
    return out
