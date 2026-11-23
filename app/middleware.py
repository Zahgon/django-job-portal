"""The request/response layers the site is built on.

Each layer is the direct replacement of one step the previous stack ran, and
they are installed in the same order, so a response that is produced early
carries exactly the headers the layers around it had already added.
"""
from __future__ import annotations

import json
import logging
import time
from urllib.parse import quote

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Match

from app.config import settings
from app.db import SessionLocal
from app.models import User


def language_from_path(path: str) -> str | None:
    parts = path.lstrip("/").split("/", 1)
    candidate = parts[0] if parts else ""
    return candidate if candidate in settings.languages else None


def path_resolves(request: Request, path: str) -> bool:
    """Whether the router serves ``path``.

    A route that lives under a language prefix only serves a path whose first
    segment is one of the languages the site publishes, so an unknown prefix is
    not a route and the request goes on to be answered as missing.
    """
    scope = dict(request.scope)
    scope["path"] = path
    scope["root_path"] = ""
    translated = language_from_path(path) is not None
    for route in request.app.router.routes:
        match, _ = route.matches(scope)
        if match not in (Match.FULL, Match.PARTIAL):
            continue
        if getattr(route, "path", "").startswith("/{language}") and not translated:
            continue
        return True
    return False


class CommonMiddleware(BaseHTTPMiddleware):
    """Adds the missing trailing slash, before anything else has been added."""

    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        if not path.endswith("/") and not path_resolves(request, path):
            if path_resolves(request, path + "/"):
                target = quote(path + "/", safe="/%:")
                if request.scope.get("query_string"):
                    target += "?" + request.scope["query_string"].decode("latin-1")
                response = RedirectResponse(target, status_code=301)
                response.headers["content-type"] = "text/html; charset=utf-8"
                return response
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """The three headers the security layer set on every response it saw."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response


class XFrameOptionsMiddleware(BaseHTTPMiddleware):
    """Refuses framing, as the previous stack's last response layer did."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def strip_language(path: str) -> str:
    language = language_from_path(path)
    if language is None:
        return path
    rest = path[len(language) + 1:]
    return rest or "/"


class LocaleMiddleware(BaseHTTPMiddleware):
    """Keeps the language prefix on the pages that carry one.

    A request without a prefix is redirected to the prefixed path when that
    path exists, trying the trailing-slash form too; a request that already
    carries one has its language reported back in ``Content-Language``.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        language = language_from_path(path)
        if language is None:
            language = self.preferred_language(request)
        request.state.language = language
        response = await call_next(request)
        response.headers.setdefault("Content-Language", language)
        if language_from_path(path) is None and response.status_code == 404:
            prefixed = "/%s%s" % (language, path)
            for candidate in (prefixed, prefixed.rstrip("/") + "/"):
                if path_resolves(request, candidate):
                    target = candidate
                    if request.scope.get("query_string"):
                        target += "?" + request.scope["query_string"].decode("latin-1")
                    redirect = RedirectResponse(target, status_code=302)
                    redirect.headers["content-type"] = "text/html; charset=utf-8"
                    return redirect
        return response

    def preferred_language(self, request: Request) -> str:
        cookie = request.cookies.get(settings.language_cookie_name)
        if cookie in settings.languages:
            return cookie
        header = request.headers.get("accept-language", "")
        for chunk in header.split(","):
            code = chunk.split(";")[0].strip().lower()
            if code in settings.languages:
                return code
            if "-" in code and code.split("-")[0] in settings.languages:
                return code.split("-")[0]
        return settings.language_code


class SessionMiddleware(BaseHTTPMiddleware):
    """A signed cookie holding the signed-in account and any pending notices."""

    def __init__(self, app):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(settings.secret_key,
                                                 salt="app.sessions")

    async def dispatch(self, request: Request, call_next):
        request.state.session = self.load(request)
        request.state.session["_messages"] = self.load_messages(request)
        request.state.session_changed = False
        had_cookie = settings.session_cookie_name in request.cookies
        signed_in_before = request.state.session.get("_auth_user_id")
        response = await call_next(request)
        session = request.state.session
        if getattr(request.state, "session_cleared", False):
            if had_cookie:
                response.delete_cookie(settings.session_cookie_name, path="/")
        elif session.get("_auth_user_id") != signed_in_before or \
                (request.state.session_changed and not had_cookie):
            response.set_cookie(
                settings.session_cookie_name,
                self.serializer.dumps({"_auth_user_id":
                                       session.get("_auth_user_id")}),
                max_age=settings.session_max_age,
                path="/",
                httponly=True,
                samesite="lax",
            )
        pending = session.get("_messages")
        if request.state.session_changed:
            if pending:
                response.set_cookie(
                    "messages", self.serializer.dumps(pending), path="/",
                    httponly=True, samesite="lax")
            elif "messages" in request.cookies:
                response.delete_cookie("messages", path="/")
        return response

    def load_messages(self, request: Request) -> list:
        raw = request.cookies.get("messages")
        if not raw:
            return []
        try:
            data = self.serializer.loads(raw, max_age=settings.session_max_age)
        except BadSignature:
            return []
        return data if isinstance(data, list) else []

    def load(self, request: Request) -> dict:
        raw = request.cookies.get(settings.session_cookie_name)
        if not raw:
            return {}
        try:
            data = self.serializer.loads(raw, max_age=settings.session_max_age)
        except BadSignature:
            return {}
        return data if isinstance(data, dict) else {}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Puts the signed-in account, when there is one, on the request."""

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        user_id = request.state.session.get("_auth_user_id")
        if user_id is not None:
            session = SessionLocal()
            try:
                user = session.get(User, int(user_id))
                if user is not None and user.is_active:
                    session.expunge(user)
                    request.state.user = user
            finally:
                session.close()
        return await call_next(request)


class MessageMiddleware(BaseHTTPMiddleware):
    """Carries one-shot notices from the request that wrote them to the next."""

    async def dispatch(self, request: Request, call_next):
        request.state.messages_read = False
        return await call_next(request)


logger = logging.getLogger("app")


class ServerErrorMiddleware(BaseHTTPMiddleware):
    """Turns an unhandled failure into the server-error page, inside the layers.

    The failure is reported before the page is returned, so a server error is
    visible in the log rather than only in the status code.
    """

    def __init__(self, app, handler):
        super().__init__(app)
        self.handler = handler

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:  # noqa: BLE001 - any failure is a server error here
            logger.exception("unhandled error serving %s %s", request.method,
                             request.url.path)
            return self.handler()
