"""Validation for the pages people fill in.

The wording of every message, the order the messages come out in and the labels
they are shown under are the ones the site already answered with, so a form
that was wrong before is wrong in the same words now.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models import (
    CompanySize, ExperienceLevel, GENDER_CHOICES, JobStatus, JobType,
    SalaryPeriod, WorkplaceType,
)
from app.security import check_password, make_password

REQUIRED = "This field is required."
INVALID_EMAIL = "Enter a valid email address."
INVALID_URL = "Enter a valid URL."
INVALID_INT = "Enter a whole number."
INVALID_DECIMAL = "Enter a number."
INVALID_DATETIME = "Enter a valid date/time."
INVALID_CHOICE = "Select a valid choice. %s is not one of the available choices."
MAX_LENGTH = "Ensure this value has at most %d characters (it has %d)."
PASSWORD_MISMATCH = "The two password fields didn’t match."
PASSWORD_TOO_SHORT = (
    "This password is too short. It must contain at least 5 characters."
)
EMAIL_TAKEN = "A user with that email already exists."

EMAIL_RE = re.compile(
    r"^(?:[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(?:\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
    r'|"(?:[\001-\010\013\014\016-\037!#-\[\]-\177]'
    r'|\\[\001-\011\013\014\016-\177])*")'
    r"@(?:(?!-)[A-Z0-9-]{1,63}(?<!-)\.)+[A-Z]{2,63}$",
    re.IGNORECASE,
)
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[^\s/?#]+[^\s]*$", re.IGNORECASE)


class ValidationError(Exception):
    """One message raised by a field's own check."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Field:
    """One input: how it is read, whether it is needed and what it is called."""

    def __init__(self, required=True, label=None, max_length=None, choices=None,
                 initial=None):
        self.required = required
        self.label = label
        self.max_length = max_length
        self.choices = choices
        self.initial = initial
        self.name = ""

    def display_label(self) -> str:
        if self.label is not None:
            return self.label
        return self.name.replace("_", " ").capitalize()

    def is_empty(self, raw) -> bool:
        return raw is None or raw == "" or raw == []

    def clean(self, raw):
        if self.is_empty(raw):
            if self.required:
                raise ValidationError(REQUIRED)
            return self.empty_value()
        value = self.to_python(raw)
        self.validate(value, raw)
        return value

    def empty_value(self):
        return ""

    def to_python(self, raw):
        return raw.strip() if isinstance(raw, str) else raw

    def validate(self, value, raw):
        if self.max_length is not None and isinstance(value, str):
            if len(value) > self.max_length:
                raise ValidationError(MAX_LENGTH % (self.max_length, len(value)))
        if self.choices is not None:
            allowed = [stored for stored, _ in self.choices]
            if value not in allowed:
                raise ValidationError(INVALID_CHOICE % raw)


class CharField(Field):
    pass


class EmailField(Field):
    def validate(self, value, raw):
        super().validate(value, raw)
        if not EMAIL_RE.match(value):
            raise ValidationError(INVALID_EMAIL)


class URLField(Field):
    def validate(self, value, raw):
        super().validate(value, raw)
        if not URL_RE.match(value):
            raise ValidationError(INVALID_URL)


class IntegerField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def to_python(self, raw):
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            raise ValidationError(INVALID_INT) from None

    def empty_value(self):
        return None


class DecimalField(Field):
    def to_python(self, raw):
        try:
            return Decimal(str(raw).strip())
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError(INVALID_DECIMAL) from None

    def empty_value(self):
        return None


class DateTimeField(Field):
    FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
               "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")

    def to_python(self, raw):
        text = str(raw).strip().replace("Z", "")
        for fmt in self.FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValidationError(INVALID_DATETIME)

    def empty_value(self):
        return None


class BooleanField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def clean(self, raw):
        if raw is None:
            return False
        return str(raw).strip().lower() not in ("", "false", "0")

    def empty_value(self):
        return False


class ModelChoiceField(Field):
    """A single row chosen by its primary key."""

    def __init__(self, loader, **kwargs):
        super().__init__(**kwargs)
        self.loader = loader

    def to_python(self, raw):
        try:
            key = int(str(raw).strip())
        except (TypeError, ValueError):
            raise ValidationError(
                "Select a valid choice. That choice is not one of the available "
                "choices.") from None
        instance = self.loader(key)
        if instance is None:
            raise ValidationError(
                "Select a valid choice. That choice is not one of the available "
                "choices.")
        return instance

    def validate(self, value, raw):
        return

    def empty_value(self):
        return None


class ModelMultipleChoiceField(Field):
    """Several rows chosen by their primary keys."""

    def __init__(self, loader, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)
        self.loader = loader

    def is_empty(self, raw) -> bool:
        return not raw

    def to_python(self, raw):
        keys = raw if isinstance(raw, (list, tuple)) else [raw]
        out = []
        for key in keys:
            try:
                number = int(str(key).strip())
            except (TypeError, ValueError):
                raise ValidationError(
                    'Select a valid choice. %s is not one of the available '
                    'choices.' % key) from None
            instance = self.loader(number)
            if instance is None:
                raise ValidationError(
                    'Select a valid choice. %s is not one of the available '
                    'choices.' % key)
            out.append(instance)
        return out

    def validate(self, value, raw):
        return

    def empty_value(self):
        return []


class Form:
    """A declared set of fields, cleaned together."""

    fields: dict[str, Field] = {}

    def __init__(self, data=None, instance=None, session=None):
        self.data = data or {}
        self.instance = instance
        self.session = session
        self.errors: dict[str, list[str]] = {}
        self.cleaned_data: dict = {}
        self.fields = {name: field for name, field in self.declare()}
        for name, field in self.fields.items():
            field.name = name

    def declare(self):
        raise NotImplementedError

    def raw(self, name):
        field = self.fields[name]
        if isinstance(field, ModelMultipleChoiceField):
            return self.data.get(name) if isinstance(self.data.get(name), list) \
                else ([self.data[name]] if self.data.get(name) else [])
        value = self.data.get(name)
        return value[0] if isinstance(value, list) and value else value

    def add_error(self, name, message):
        self.errors.setdefault(name, []).append(message)

    def is_valid(self) -> bool:
        self.errors = {}
        self.cleaned_data = {}
        for name, field in self.fields.items():
            try:
                self.cleaned_data[name] = field.clean(self.raw(name))
            except ValidationError as error:
                self.add_error(name, error.message)
                continue
            hook = getattr(self, "clean_" + name, None)
            if hook is not None:
                try:
                    self.cleaned_data[name] = hook()
                except ValidationError as error:
                    self.add_error(name, error.message)
        if not self.errors:
            try:
                self.clean()
            except ValidationError as error:
                self.add_error("__all__", error.message)
        return not self.errors

    def clean(self):
        return

    @property
    def non_field_errors(self) -> list[str]:
        return self.errors.get("__all__", [])

    def __iter__(self):
        for name in self.fields:
            yield BoundField(self, name)

    def __getattr__(self, name):
        fields = self.__dict__.get("fields") or {}
        if name in fields:
            return BoundField(self, name)
        raise AttributeError(name)

    def __getitem__(self, name):
        return BoundField(self, name)

    def field_errors(self) -> list[tuple[str, str]]:
        """Every field error as (label, message), in declaration order."""
        out = []
        for name, field in self.fields.items():
            for message in self.errors.get(name, []):
                out.append((field.display_label(), message))
        return out

    def value(self, name):
        raw = self.raw(name)
        if raw not in (None, ""):
            return raw
        if self.instance is not None:
            return getattr(self.instance, name, "")
        return ""


class Widget:
    """What the markup needs to draw one input."""

    def __init__(self, input_type: str, attrs: dict):
        self.input_type = input_type
        self.attrs = attrs


class BoundField:
    """One field together with the data and the errors of this submission."""

    TYPES = {"EmailField": "email", "IntegerField": "number",
             "DecimalField": "number", "URLField": "url",
             "DateTimeField": "date"}

    def __init__(self, form: Form, name: str):
        self.form = form
        self.name = name
        self.field = self

    @property
    def _field(self) -> Field:
        return self.form.fields[self.name]

    @property
    def label(self) -> str:
        return self._field.display_label()

    @property
    def errors(self) -> list[str]:
        return self.form.errors.get(self.name, [])

    @property
    def value(self):
        return self.form.value(self.name)

    @property
    def widget(self) -> Widget:
        field = self._field
        kind = self.TYPES.get(type(field).__name__, "text")
        if self.name.startswith("password"):
            kind = "password"
        return Widget(kind, {"placeholder": PLACEHOLDERS.get(self.name, "")})


PLACEHOLDERS = {
    "first_name": "Enter First Name",
    "last_name": "Enter Last Name",
    "email": "Enter Email",
    "password1": "Enter Password",
    "password2": "Confirm Password",
    "password": "Enter Password",
}
