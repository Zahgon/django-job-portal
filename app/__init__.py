"""The application factory.

``create_app`` builds the whole site: the layers in the order they ran before,
the routes that are addressed without a language prefix, and the translated
pages underneath one.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response

from app.config import settings

ERROR_PAGES = {
    404: ("Not Found", "<h1>Not Found</h1><p>The requested resource was not "
                       "found on this server.</p>"),
    403: ("403 Forbidden", "<h1>403 Forbidden</h1>"),
    405: ("405 Method Not Allowed", "<h1>405 Method Not Allowed</h1>"),
    500: ("Server Error (500)", "<h1>Server Error (500)</h1>"),
}


class RedirectRequired(Exception):
    """Raised to send a visitor somewhere else than the page they asked for."""

    def __init__(self, target: str, status_code: int = 302):
        super().__init__(target)
        self.target = target
        self.status_code = status_code


def known_language(request: Request) -> str:
    """Refuse a language the site does not publish, so the path is simply missing."""
    language = request.path_params.get("language")
    if language not in settings.languages:
        raise HTTPException(status_code=404)
    request.state.language = language
    return language


def error_page(status_code: int) -> Response:
    title, body = ERROR_PAGES.get(status_code, ("Error", "<h1>Error</h1>"))
    html = ("<!doctype html><html lang=\"en\"><head><title>%s</title></head>"
            "<body>%s</body></html>" % (title, body))
    return Response(html, status_code=status_code,
                    media_type="text/html; charset=utf-8")


def create_app() -> FastAPI:
    """Build the application, layers outermost first."""
    app = FastAPI(docs_url="/api/docs", redoc_url="/api/redoc",
                  openapi_url="/api/openapi.json", title="Jobs Portal API")
    # A path that only matches with a language prefix is not the same path with
    # a slash added, so the router must not invent that redirect.
    app.router.redirect_slashes = False

    # Imported here so that importing the package does not pull in the whole
    # application: the helpers are usable on their own.
    from app import api, web, webauth
    from app.apicore import APIError, envelope
    from app.middleware import (
        AuthenticationMiddleware, CommonMiddleware, LocaleMiddleware,
        MessageMiddleware, SecurityHeadersMiddleware, ServerErrorMiddleware,
        SessionMiddleware, XFrameOptionsMiddleware,
    )

    app.include_router(api.router, prefix="/api")
    app.include_router(webauth.unprefixed_router)
    language_router = APIRouter()
    language_router.include_router(web.router)
    language_router.include_router(webauth.router)
    app.include_router(language_router, prefix="/{language}",
                       dependencies=[Depends(known_language)])

    @app.exception_handler(APIError)
    async def api_error(request: Request, error: APIError) -> Response:
        response = JSONResponse(envelope(error), status_code=error.status_code)
        allow = getattr(error, "allow", None) or \
            getattr(request.state, "api_allow", None)
        if allow:
            response.headers["Allow"] = allow
        return response

    @app.exception_handler(RedirectRequired)
    async def redirect_required(request: Request,
                                error: RedirectRequired) -> Response:
        response = Response(b"", status_code=error.status_code,
                            media_type="text/html; charset=utf-8")
        response.headers["Location"] = error.target
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                envelope(APIError.detail(error.status_code, str(error.detail))),
                status_code=error.status_code)
        if error.status_code == 405:
            # A refused method answers with the methods it does serve, which
            # always include the one that only reports them, and no body.
            allow = (error.headers or {}).get("Allow", "")
            return Response(b"", status_code=405,
                            media_type="text/html; charset=utf-8",
                            headers={"Allow": allow} if allow else None)
        return error_page(error.status_code)

    @app.exception_handler(Exception)
    async def server_error(request: Request, error: Exception) -> Response:
        return error_page(500)

    app.add_middleware(ServerErrorMiddleware, handler=lambda: error_page(500))
    app.add_middleware(XFrameOptionsMiddleware)
    app.add_middleware(MessageMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(SessionMiddleware)
    app.add_middleware(LocaleMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CommonMiddleware)
    return app
