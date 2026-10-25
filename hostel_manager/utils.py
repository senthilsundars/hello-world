"""Validation and date helpers. All dates are stored as ISO strings (YYYY-MM-DD)."""
import re
from datetime import date, datetime

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M"


class ValidationError(ValueError):
    """Raised with a user-friendly message when form input is invalid."""


def today_str():
    return date.today().strftime(DATE_FMT)


def now_str():
    return datetime.now().strftime(DATETIME_FMT)


def current_month():
    return date.today().strftime("%Y-%m")


def required(value, label):
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{label} is required.")
    return value


def parse_date(value, label, allow_empty=False):
    value = (value or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ValidationError(f"{label} is required.")
    try:
        return datetime.strptime(value, DATE_FMT).strftime(DATE_FMT)
    except ValueError:
        raise ValidationError(f"{label} must be a valid date in YYYY-MM-DD format.")


def parse_datetime(value, label, allow_empty=False):
    value = (value or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ValidationError(f"{label} is required.")
    for fmt in (DATETIME_FMT, DATE_FMT):
        try:
            return datetime.strptime(value, fmt).strftime(DATETIME_FMT)
        except ValueError:
            continue
    raise ValidationError(f"{label} must be in YYYY-MM-DD HH:MM format.")


def parse_month(value, label):
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise ValidationError(f"{label} must be in YYYY-MM format (e.g. 2025-01).")


def parse_amount(value, label, allow_zero=True):
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        raise ValidationError(f"{label} is required.")
    try:
        number = round(float(text), 2)
    except ValueError:
        raise ValidationError(f"{label} must be a number.")
    if number != number or number in (float("inf"), float("-inf")):
        raise ValidationError(f"{label} must be a number.")
    if number < 0 or (number == 0 and not allow_zero):
        raise ValidationError(f"{label} must be {'greater than' if not allow_zero else 'at least'} 0.")
    return number


def parse_int(value, label, minimum=None):
    text = str(value if value is not None else "").strip()
    try:
        number = int(text)
    except ValueError:
        raise ValidationError(f"{label} must be a whole number.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{label} must be at least {minimum}.")
    return number


def optional_phone(value, label, required_field=False):
    value = (value or "").strip()
    if not value:
        if required_field:
            raise ValidationError(f"{label} is required.")
        return ""
    if not re.fullmatch(r"[0-9+\-\s]{7,15}", value):
        raise ValidationError(f"{label} must contain 7-15 digits (digits, +, - and spaces allowed).")
    return value


def month_range(start_month, end_month):
    """Yield YYYY-MM strings from start to end inclusive."""
    y, m = map(int, start_month.split("-"))
    ey, em = map(int, end_month.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1
