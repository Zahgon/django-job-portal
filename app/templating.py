"""The template environment the pages are rendered with.

The filters and helpers are the ones the pages already used, so the markup
needed only its syntax changed and not its meaning.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import HTMLResponse

from app.config import settings
from app.models import Applicant, Favorite
from app.urls import reverse

TIME_UNITS = (
    ("year", 60 * 60 * 24 * 365),
    ("month", 60 * 60 * 24 * 30),
    ("week", 60 * 60 * 24 * 7),
    ("day", 60 * 60 * 24),
    ("hour", 60 * 60),
    ("minute", 60),
)

DATE_FORMATS = {
    "d": "%d", "j": "%-d", "m": "%m", "n": "%-m", "Y": "%Y", "y": "%y",
    "M": "%b", "F": "%B", "D": "%a", "l": "%A", "H": "%H", "i": "%M",
    "s": "%S", "P": "%I:%M %p", "N": "%b.",
}


def do_add(value, arg):
    """Django's ``add``: numbers when it can, strings when it cannot."""
    try:
        return int(value) + int(arg)
    except (TypeError, ValueError):
        try:
            return value + arg
        except TypeError:
            return ""


def do_default_if_none(value, arg):
    return arg if value is None else value


def do_default(value, arg):
    return value if value else arg


def do_date(value, fmt="N j, Y"):
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    out = []
    for char in fmt:
        out.append(value.strftime(DATE_FORMATS[char]) if char in DATE_FORMATS
                   else char)
    return "".join(out)


def do_timesince(value, now=None):
    """How long ago a moment was, to the same two units as before."""
    if value in (None, ""):
        return ""
    now = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    seconds = int((now - value).total_seconds())
    if seconds < 60:
        return "0\xa0minutes"
    parts = []
    for name, size in TIME_UNITS:
        count = seconds // size
        if count:
            parts.append("%d\xa0%s%s" % (count, name, "s" if count != 1 else ""))
            seconds -= count * size
            if len(parts) == 2:
                break
            if not parts:
                break
    return ",\xa0".join(parts) if parts else "0\xa0minutes"


def do_stringformat(value, fmt):
    try:
        return ("%" + str(fmt)) % value
    except (TypeError, ValueError):
        return ""


def do_pluralize(value, suffixes="s"):
    singular, _, plural = suffixes.partition(",")
    if not plural:
        singular, plural = "", singular
    try:
        count = len(value)
    except TypeError:
        try:
            count = int(value)
        except (TypeError, ValueError):
            return ""
    return singular if count == 1 else plural


def do_intcomma(value):
    try:
        return "{:,}".format(int(value))
    except (TypeError, ValueError):
        return value


def do_truncatewords(value, count):
    words = str(value).split()
    if len(words) <= int(count):
        return " ".join(words)
    return " ".join(words[:int(count)]) + "…"


def do_truncatewords_html(value, count):
    return do_truncatewords(re.sub(r"<[^>]+>", "", str(value)), count)


def do_linebreaks(value):
    text = escape(str(value)).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.replace("\n", Markup("<br>")) for p in text.split("\n\n")]
    return Markup("".join("<p>%s</p>" % p for p in paragraphs))


environment = Environment(
    loader=FileSystemLoader(str(settings.templates_dir)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
)
environment.filters.update({
    "add": do_add,
    "default_if_none": do_default_if_none,
    "default": do_default,
    "date": do_date,
    "timesince": do_timesince,
    "stringformat": do_stringformat,
    "pluralize": do_pluralize,
    "intcomma": do_intcomma,
    "truncatewords": do_truncatewords,
    "truncatewords_html": do_truncatewords_html,
    "linebreaks": do_linebreaks,
    "escape": escape,
})


def page_context(request: Request, session=None, extra: dict | None = None) -> dict:
    """Everything every page is given, plus whatever the view adds."""
    language = getattr(request.state, "language", settings.language_code)
    user = getattr(request.state, "user", None)
    query = dict(request.query_params)

    def url(name, *args):
        return reverse(name, *args, language=language)

    def url_replace(field, value):
        params = dict(query)
        params[str(field)] = str(value)
        return urlencode(params)

    def is_favorited(job):
        if session is None or user is None:
            return False
        return session.scalar(
            select(Favorite).where(Favorite.job_id == job.id,
                                   Favorite.user_id == user.id,
                                   Favorite.soft_deleted.is_(False))
        ) is not None

    def is_already_applied(job, _user):
        if session is None or user is None:
            return False
        return session.scalar(
            select(Applicant).where(Applicant.job_id == job.id,
                                    Applicant.user_id == user.id)
        ) is not None

    def tag_exists(identifier, tags):
        return bool(tags) and str(identifier) in [str(t) for t in tags]

    context = {
        "request": request,
        "request_get": query,
        "user": user,
        "language": language,
        "languages": [("en", "English"), ("bn", "Bengali")],
        "LANGUAGE_CODE": language,
        "messages": pop_messages(request),
        "url": url,
        "static": lambda path: settings.static_url + str(path).lstrip("/"),
        "url_replace": url_replace,
        "now": lambda fmt="Y": do_date(datetime.now(timezone.utc), fmt),
        "is_favorited": is_favorited,
        "is_already_applied": is_already_applied,
        "tag_exists": tag_exists,
        "csrf_token": "",
        "url_name": getattr(request.state, "url_name", ""),
        "_": lambda text: text,
    }
    context.update(extra or {})
    return context


def pop_messages(request: Request) -> list:
    """The notices stored by the request that produced this page."""
    session = getattr(request.state, "session", None)
    if not session:
        return []
    stored = session.pop("_messages", [])
    if stored:
        request.state.session_changed = True
    return [Message(tag, text) for tag, text in stored]


class Message:
    """One notice, with the tag the markup styles it by."""

    def __init__(self, tags: str, text: str):
        self.tags = tags
        self.text = text

    def __str__(self) -> str:
        return self.text

    def __html__(self) -> str:
        return escape(self.text)


def add_message(request: Request, tags: str, text: str) -> None:
    session = getattr(request.state, "session", None)
    if session is None:
        return
    session.setdefault("_messages", []).append([tags, text])
    request.state.session_changed = True


def render(request: Request, template: str, context: dict | None = None,
           status_code: int = 200, session=None) -> HTMLResponse:
    """Render one page with the shared context."""
    body = environment.get_template(template).render(
        page_context(request, session=session, extra=context))
    return HTMLResponse(body, status_code=status_code)
