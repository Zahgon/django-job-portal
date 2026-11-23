"""The wording the forms answer with, and what a failed submission writes."""
from __future__ import annotations

from sqlalchemy import select

from app.models import User
from tests.conftest import PASSWORD, sign_in


def register(client, **overrides):
    data = {"first_name": "New", "last_name": "Candidate",
            "email": "new.candidate@example.com", "gender": "male",
            "password1": PASSWORD, "password2": PASSWORD}
    data.update(overrides)
    return client.post("/en/employee/register/", data=data)


class TestSigningUp:
    def test_a_complete_form_creates_the_account(self, client, database):
        reply = register(client)
        assert reply.status_code == 302
        assert reply.headers["location"] == "/en/login/"
        created = database.scalar(
            select(User).where(User.email == "new.candidate@example.com"))
        assert created is not None and created.role == "employee"

    def test_a_missing_name_is_reported_and_writes_nothing(self, client, database):
        before = len(database.scalars(select(User)).all())
        reply = register(client, first_name="")
        assert reply.status_code == 200
        assert "This field is required." in reply.text
        assert len(database.scalars(select(User)).all()) == before

    def test_a_missing_gender_has_its_own_wording(self, client):
        assert "Gender is required" in register(client, gender="").text

    def test_a_malformed_address_is_reported(self, client):
        assert "Enter a valid email address." in register(client, email="nope").text

    def test_an_address_in_use_is_reported(self, client, employee):
        assert "A user with that email already exists." in \
            register(client, email=employee.email).text

    def test_two_different_passwords_are_reported(self, client):
        assert "didn’t match" in register(client, password2="Other.1").text

    def test_a_short_password_is_reported(self, client):
        reply = register(client, password1="a1", password2="a1")
        assert "This password is too short." in reply.text


class TestPostingAJob:
    def test_a_deadline_in_the_past_is_refused(self, client, employer, posting):
        sign_in(client, employer.email)
        reply = client.post("/en/employer/dashboard/jobs/create/", data={
            "company": str(posting.company_id), "category": str(posting.category_id),
            "title": "Staff Engineer", "description": "Lead.", "location": "Dhaka",
            "type": "1", "workplace_type": "remote", "experience_level": "lead",
            "application_deadline": "2000-01-01", "status": "published",
            "salary": "1", "salary_currency": "BDT", "salary_period": "month",
            "vacancy": "1", "tags": [str(posting.tags[0].id)]})
        assert reply.status_code == 200
        assert "be before today" in reply.text
