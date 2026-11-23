"""The JSON API: its payloads, its permissions and its error envelope."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Applicant
from tests.conftest import bearer


class TestPublicCollections:
    def test_the_postings_are_paged(self, client, posting):
        reply = client.get("/api/jobs/")
        assert reply.status_code == 200
        body = reply.json()
        assert set(body) == {"count", "next", "previous", "results"}
        assert body["count"] == 1
        assert body["results"][0]["title"] == "Backend Engineer"

    def test_a_posting_carries_its_labels_and_its_relations(self, client, posting):
        body = client.get("/api/jobs/%d/" % posting.id).json()
        assert body["type_display"] == "Full time"
        assert body["company"]["name"] == "Acme Corp"
        assert body["category"]["slug"] == "engineering"
        assert body["job_tags"] == [{"id": posting.tags[0].id, "name": "python"}]

    def test_a_page_past_the_end_is_not_found(self, client, posting):
        reply = client.get("/api/jobs/?page=99")
        assert reply.status_code == 404
        assert reply.json()["message"] == "Invalid page."

    def test_a_refused_method_comes_before_anything_else(self, client):
        reply = client.post("/api/jobs/", json={})
        assert reply.status_code == 405
        assert reply.json()["errors"] == [{"detail": 'Method "POST" not allowed.'}]


class TestAccounts:
    def test_signing_in_returns_a_pair_of_tokens(self, client, employee):
        reply = client.post("/api/login/",
                            json={"email": employee.email,
                                  "password": "Abcdefgh.1"})
        assert reply.status_code == 200
        assert set(reply.json()) == {"refresh", "access"}

    def test_a_wrong_password_is_refused(self, client, employee):
        reply = client.post("/api/login/",
                            json={"email": employee.email, "password": "wrong"})
        assert reply.status_code == 401
        assert reply.json()["message"] == \
            "No active account found with the given credentials"

    def test_the_profile_needs_a_token(self, client):
        reply = client.get("/api/employee/profile/")
        assert reply.status_code == 401
        assert reply.json()["message"] == \
            "Authentication credentials were not provided."

    def test_the_wrong_role_is_refused(self, client, employer):
        reply = client.get("/api/employee/profile/",
                           headers=bearer(client, employer.email))
        assert reply.status_code == 403


class TestApplying:
    def test_a_candidate_applies_once(self, client, database, posting, employee):
        headers = bearer(client, employee.email)
        first = client.post("/api/apply-job/%d/" % posting.id,
                            json={"job": posting.id}, headers=headers)
        assert first.status_code == 201
        second = client.post("/api/apply-job/%d/" % posting.id,
                             json={"job": posting.id}, headers=headers)
        assert second.status_code == 400
        assert second.json()["errors"] == [
            {"non_field_errors": "You have already applied to this job"}]
        assert len(database.scalars(select(Applicant)).all()) == 1

    def test_an_unknown_posting_is_reported(self, client, posting, employee):
        reply = client.post("/api/apply-job/9999/", json={"job": 9999},
                            headers=bearer(client, employee.email))
        assert reply.status_code == 400
        assert reply.json()["errors"] == [
            {"job": 'Invalid pk "9999" - object does not exist.'}]
