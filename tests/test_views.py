"""The pages: what they answer, who may see them and what they link to."""
from __future__ import annotations

from tests.conftest import sign_in


class TestRouting:
    def test_a_path_without_a_language_is_redirected(self, client):
        reply = client.get("/jobs/")
        assert reply.status_code == 302
        assert reply.headers["location"] == "/en/jobs/"

    def test_a_missing_trailing_slash_is_added(self, client):
        reply = client.get("/en/jobs")
        assert reply.status_code == 301
        assert reply.headers["location"] == "/en/jobs/"

    def test_an_unpublished_language_is_not_found(self, client):
        assert client.get("/xx/jobs/").status_code == 404

    def test_a_refused_method_reports_what_it_serves(self, client):
        reply = client.post("/en/jobs/")
        assert reply.status_code == 405
        assert set(reply.headers["allow"].replace(" ", "").split(",")) == {
            "GET", "HEAD", "OPTIONS"}


class TestPages:
    def test_the_listing_shows_the_open_postings(self, client, posting):
        reply = client.get("/en/jobs/")
        assert reply.status_code == 200
        assert "/en/jobs/%d/" % posting.id in reply.text
        assert ">1</strong> open job" in reply.text

    def test_a_filled_posting_is_not_listed(self, client, database, posting):
        posting.filled = True
        database.commit()
        assert ">0</strong> open job" in client.get("/en/jobs/").text

    def test_a_posting_has_its_own_page(self, client, posting):
        reply = client.get("/en/jobs/%d/" % posting.id)
        assert reply.status_code == 200
        assert "Backend Engineer" in reply.text

    def test_an_unknown_posting_is_not_found(self, client):
        assert client.get("/en/jobs/9999/").status_code == 404


class TestPermissions:
    def test_an_anonymous_visitor_is_sent_to_sign_in(self, client):
        reply = client.get("/en/employer/dashboard/")
        assert reply.status_code == 302
        assert reply.headers["location"] == \
            "/en/login/?next=/en/employer/dashboard/"

    def test_the_wrong_role_is_refused(self, client, employee):
        sign_in(client, employee.email)
        assert client.get("/en/employer/dashboard/").status_code == 403

    def test_the_right_role_is_let_in(self, client, employer, posting):
        sign_in(client, employer.email)
        assert client.get("/en/employer/dashboard/").status_code == 200


class TestSigningIn:
    def test_a_wrong_password_is_refused_in_the_same_words(self, client, employee):
        reply = client.post("/en/login/",
                            data={"email": employee.email, "password": "wrong"})
        assert reply.status_code == 200
        assert "User Does Not Exist." in reply.text

    def test_signing_out_clears_the_session(self, client, employee):
        sign_in(client, employee.email)
        reply = client.get("/en/logout/")
        assert reply.status_code == 302
        assert reply.headers["location"] == "/login"
