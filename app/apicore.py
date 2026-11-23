"""The shared machinery behind the JSON API.

Errors leave through one envelope, collections are paged the same way they were
before, and every answer carries the ``Allow`` header its endpoint advertises.
"""
from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.security import TokenError, read_token

NOT_AUTHENTICATED = "Authentication credentials were not provided."
PERMISSION_DENIED = "You do not have permission to perform this action."
INVALID_PAGE = "Invalid page."


class APIError(Exception):
    """An error that leaves through the shared envelope."""

    def __init__(self, status_code: int, errors: list[dict], message: str):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors
        self.message = message

    @classmethod
    def detail(cls, status_code: int, text: str) -> "APIError":
        return cls(status_code, [{"detail": text}], text)

    @classmethod
    def fields(cls, errors: dict[str, list[str]]) -> "APIError":
        rows = [{name: messages[0]} for name, messages in errors.items()]
        message = "".join(messages[0] + " " for messages in errors.values())
        return cls(400, rows, message)


def not_authenticated() -> APIError:
    return APIError.detail(401, NOT_AUTHENTICATED)


def permission_denied() -> APIError:
    return APIError.detail(403, PERMISSION_DENIED)


def method_not_allowed(method: str) -> APIError:
    return APIError.detail(405, 'Method "%s" not allowed.' % method)


def not_found(what: str) -> APIError:
    return APIError.detail(404, "No %s matches the given query." % what)


def envelope(error: APIError) -> dict[str, Any]:
    return {"errors": error.errors, "status": False, "message": error.message}


def api_response(payload: Any, status_code: int = 200,
                 allow: str | None = None) -> JSONResponse:
    response = JSONResponse(payload, status_code=status_code)
    response.headers["Content-Type"] = "application/json"
    if allow:
        response.headers["Allow"] = allow
    return response


def check_methods(request: Request, allowed: Iterable[str], allow_header: str):
    """Refuse a method this endpoint does not serve, before anything else."""
    request.state.api_allow = allow_header
    if request.method not in allowed:
        error = method_not_allowed(request.method)
        error.allow = allow_header
        raise error


def bearer_user(request: Request, session):
    """The account a bearer token names, or ``None`` when there is no token."""
    from app.models import User  # imported here to keep the import graph flat

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    try:
        claims = read_token(token, settings.secret_key)
    except TokenError:
        raise APIError(
            401,
            [{"detail": "Given token not valid for any token type"},
             {"code": "token_not_valid"}],
            "Given token not valid for any token type",
        ) from None
    if claims.get("token_type") != "access":
        raise APIError(
            401,
            [{"detail": "Given token not valid for any token type"},
             {"code": "token_not_valid"}],
            "Given token not valid for any token type",
        )
    user = session.get(User, int(claims.get("user_id", 0)))
    if user is None or not user.is_active:
        raise APIError(
            401,
            [{"detail": "Given token not valid for any token type"},
             {"code": "token_not_valid"}],
            "Given token not valid for any token type",
        )
    return user


def require_user(request: Request, session):
    user = bearer_user(request, session)
    if user is None:
        raise not_authenticated()
    return user


def require_role(request: Request, session, role: str):
    user = require_user(request, session)
    if user.role != role:
        raise permission_denied()
    return user


class Paginator:
    """Page a collection the way the previous API did, links included."""

    def __init__(self, request: Request, page_size: int):
        self.request = request
        self.page_size = page_size

    def page(self, rows: list) -> dict:
        count = len(rows)
        raw = self.request.query_params.get("page", "1")
        try:
            number = int(raw)
        except (TypeError, ValueError):
            raise APIError.detail(404, INVALID_PAGE) from None
        if number < 1:
            raise APIError.detail(404, INVALID_PAGE)
        start = (number - 1) * self.page_size
        if start >= count and (count or number != 1):
            raise APIError.detail(404, INVALID_PAGE)
        window = rows[start:start + self.page_size]
        return {
            "count": count,
            "next": self.link(number + 1) if start + self.page_size < count
            else None,
            "previous": self.link(number - 1) if number > 1 else None,
            "results": window,
        }

    def link(self, number: int) -> str:
        params = dict(self.request.query_params)
        if number <= 1:
            params.pop("page", None)
        else:
            params["page"] = str(number)
        base = str(self.request.url.replace(query="", fragment=""))
        return base + ("?" + urlencode(params) if params else "")
