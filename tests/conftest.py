"""Shared test setup.

Each test works against its own copy of a database the project's own Alembic
revisions built, so the suite exercises the schema the deployment has and no
test can see another test's writes.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, set_database_url  # noqa: E402
from app.models import Category, Company, Job, Tag, User  # noqa: E402
from app.security import make_password  # noqa: E402

PASSWORD = "Abcdefgh.1"


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    """One migrated database, built once and copied per test."""
    path = tmp_path_factory.mktemp("schema") / "template.sqlite3"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(ROOT), capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": "sqlite:///%s" % path,
             "PYTHONPATH": str(ROOT)})
    assert result.returncode == 0, result.stdout + result.stderr
    return path


@pytest.fixture
def database(template, tmp_path):
    path = tmp_path / "test.sqlite3"
    shutil.copyfile(template, path)
    set_database_url("sqlite:///%s" % path)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def employer(database):
    user = User(email="employer@example.com", role="employer", first_name="Acme",
                last_name="Corp", gender="", password=make_password(PASSWORD),
                is_active=True, is_staff=False, is_superuser=False,
                date_joined=datetime.now(timezone.utc))
    database.add(user)
    database.commit()
    return user


@pytest.fixture
def employee(database):
    user = User(email="employee@example.com", role="employee", first_name="Ada",
                last_name="Lovelace", gender="female",
                password=make_password(PASSWORD), is_active=True, is_staff=False,
                is_superuser=False, date_joined=datetime.now(timezone.utc))
    database.add(user)
    database.commit()
    return user


@pytest.fixture
def posting(database, employer):
    category = Category(name="Engineering", slug="engineering",
                        description="Engineering roles")
    tag = Tag(name="python")
    company = Company(user_id=employer.id, name="Acme Corp", size="3",
                      is_verified=False, featured=False)
    company.ensure_slug()
    database.add_all([category, tag, company])
    database.commit()
    job = Job(user_id=employer.id, company_id=company.id, category_id=category.id,
              title="Backend Engineer", description="Build things.",
              responsibilities="", requirements="", location="Dhaka", type="1",
              workplace_type="remote", experience_level="senior",
              application_deadline=datetime.now(timezone.utc) + timedelta(days=30),
              filled=False, status="published", salary=90000,
              salary_currency="BDT", salary_period="month", vacancy=1,
              is_featured=False)
    job.ensure_slug()
    job.tags.append(tag)
    database.add(job)
    database.commit()
    return job


@pytest.fixture
def client(database):
    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://testserver",
                    follow_redirects=False) as test_client:
        yield test_client


def sign_in(client, email):
    reply = client.post("/en/login/", data={"email": email, "password": PASSWORD})
    assert reply.status_code == 302, reply.text[:400]
    return client


def bearer(client, email):
    reply = client.post("/api/login/", json={"email": email, "password": PASSWORD})
    assert reply.status_code == 200, reply.text[:400]
    return {"Authorization": "Bearer " + reply.json()["access"]}
