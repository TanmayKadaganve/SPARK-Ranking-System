"""Unlimited-size signed integer storage and form parsing helpers.

SQLite INTEGER values have a signed 64-bit limit. Storing decimal digits in a
TEXT column avoids that ceiling while these helpers expose ordinary Python
integers to application code.
"""
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import models


INTEGER_TEXT_RE = re.compile(r"^[+-]?\d+$")
_CHUNK_BASE = 1_000_000_000


def parse_unlimited_integer(value):
    if isinstance(value, bool):
        raise ValueError("Boolean values are not point amounts.")
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not INTEGER_TEXT_RE.fullmatch(text):
        raise ValueError("Enter a whole number, with an optional + or - sign.")
    negative = text.startswith("-")
    digits = text.lstrip("+-").lstrip("0") or "0"
    result = 0
    # Parse small chunks so Python's defensive limit on enormous int strings
    # does not become an application-level point limit.
    first = len(digits) % 9 or 9
    result = int(digits[:first])
    for offset in range(first, len(digits), 9):
        result = result * _CHUNK_BASE + int(digits[offset : offset + 9])
    return -result if negative and result else result


def unlimited_integer_to_text(value):
    number = parse_unlimited_integer(value)
    if number == 0:
        return "0"
    negative = number < 0
    number = abs(number)
    chunks = []
    while number:
        number, remainder = divmod(number, _CHUNK_BASE)
        chunks.append(remainder)
    text = str(chunks.pop()) + "".join(f"{chunk:09d}" for chunk in reversed(chunks))
    return "-" + text if negative else text


def format_points(value):
    """Format arbitrary-size points with thousands separators."""
    text = unlimited_integer_to_text(value)
    sign = "-" if text.startswith("-") else ""
    digits = text.lstrip("-")
    first = len(digits) % 3 or 3
    return sign + digits[:first] + "".join("," + digits[pos : pos + 3] for pos in range(first, len(digits), 3))


class UnlimitedIntegerField(models.TextField):
    """Text-backed model field that returns Python's arbitrary-precision int."""

    description = "An unlimited-size signed integer stored as decimal text"

    def to_python(self, value):
        if value is None:
            return None
        try:
            return parse_unlimited_integer(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(str(exc), code="invalid") from exc

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return parse_unlimited_integer(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        try:
            return unlimited_integer_to_text(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(str(exc), code="invalid") from exc

    def formfield(self, **kwargs):
        defaults = {"form_class": UnlimitedIntegerFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class UnlimitedIntegerFormField(forms.Field):
    widget = forms.TextInput

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return parse_unlimited_integer(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(str(exc), code="invalid") from exc

    def prepare_value(self, value):
        if value is None or value == "":
            return ""
        try:
            return unlimited_integer_to_text(value)
        except (TypeError, ValueError):
            return value
