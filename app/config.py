"""Runtime settings, read from the environment the deployment already sets."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """One place for everything the application reads out of its environment."""

    def __init__(self) -> None:
        self.base_dir = BASE_DIR
        self.secret_key = os.environ.get(
            "SECRET_KEY", "@pzqp#x^+#(olu#wy(6=mi9&a8n+g&x#af#apn07@j=5oin=xb"
        )
        self.debug = _flag("DEBUG", False)
        self.database_url = os.environ.get(
            "DATABASE_URL", "sqlite:///" + str(BASE_DIR / "db.sqlite3")
        )
        self.languages = ("en", "bn")
        self.language_code = "en"
        self.language_cookie_name = "django_language"
        self.session_cookie_name = "sessionid"
        self.session_max_age = 1209600
        self.static_url = "/static/"
        self.static_root = BASE_DIR / "staticfiles"
        self.static_dir = BASE_DIR / "static"
        self.media_url = "/media/"
        self.media_root = BASE_DIR / "mediafiles"
        self.templates_dir = BASE_DIR / "templates"
        self.login_url = "/login/"
        self.login_redirect_url = "/"
        self.logout_redirect_url = "/"
        self.access_token_lifetime = 86400
        self.refresh_token_lifetime = 86400
        self.jobs_page_size = 5
        self.api_job_page_size = 9
        self.api_company_page_size = 12
        self.dashboard_page_size = 10
        self.applicants_page_size = 6


settings = Settings()
