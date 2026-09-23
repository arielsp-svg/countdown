"""Deciding which systems are due for an alert (R5, R6, R10, R11)."""
import calendar
import logging
from datetime import date

log = logging.getLogger(__name__)


def add_months(start: date, months: int) -> date:
    """`start` moved forward by whole calendar months, clamped to month end."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def tier_for(ro_date: date, tiers, today: date):
    """The tightest tier whose window contains this RO date, else None.

    Tiers are sorted widest first, so the last match is the tightest one and
    that is the cadence that applies (R6: the tighter tier wins).
    """
    match = None
    for tier in tiers:
        try:
            months = int(tier["months"])
        except (KeyError, TypeError, ValueError):
            continue
        if months <= 0:
            continue
        if ro_date <= add_months(today, months):
            if match is None or months < int(match["months"]):
                match = tier
    return match


def interval_days(tier) -> int:
    try:
        days = int(tier.get("every_days") or 0)
    except (TypeError, ValueError):
        days = 0
    # A blank or zero frequency would alert every single day (R7 edge case).
    return days if days > 0 else 30


def department_matches(row_department: str, user_department: str) -> bool:
    """R5: only rows in the user's department count. Blank never matches."""
    a = (row_department or "").strip().casefold()
    b = (user_department or "").strip().casefold()
    return bool(a) and bool(b) and a == b


def due_systems(rows, state, today=None):
    """Rows that should raise an alert now, each with its tier."""
    today = today or date.today()
    tiers = state.tiers
    department = state.department
    due = []
    for row in rows:
        if not department_matches(row.department, department):
            continue
        if row.ro_date <= today:
            # Already passed. The spec leaves overdue behaviour open; nothing is
            # raised, and the row is reported to the admin window instead.
            continue
        tier = tier_for(row.ro_date, tiers, today)
        if tier is None:
            continue
        key = row.key
        snooze = state.snooze_until(key)
        if snooze and snooze > today:
            continue
        last = state.last_alert(key)
        if last is not None and (today - last).days < interval_days(tier):
            continue
        due.append((row, tier))
    due.sort(key=lambda item: item[0].ro_date)
    return due


def overdue_systems(rows, state, today=None):
    """Rows in the user's department whose RO date has passed."""
    today = today or date.today()
    return [
        row for row in rows
        if department_matches(row.department, state.department) and row.ro_date <= today
    ]
