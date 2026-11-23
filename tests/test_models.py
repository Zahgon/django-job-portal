"""The rows the application stores, and the way it derives their fields."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Applicant, Company, Favorite, Job
from app.security import check_password, make_password
from app.text import slugify


class TestSlugs:
    def test_company_slug_is_name_and_owner(self, database, employer):
        company = Company(user_id=employer.id, name="Globex Industries", size="")
        company.ensure_slug()
        assert company.slug == slugify("Globex Industries-%s" % employer.id)

    def test_job_slug_is_title_company_and_owner(self, posting):
        assert posting.slug == slugify("Backend Engineer-%s-%s"
                                       % (posting.company_id, posting.user_id))

    def test_an_existing_slug_is_left_alone(self, posting):
        posting.slug = "kept"
        posting.ensure_slug()
        assert posting.slug == "kept"


class TestChoices:
    def test_labels(self, posting):
        assert posting.get_type_display() == "Full time"
        assert posting.get_workplace_type_display() == "Remote"
        assert posting.get_experience_level_display() == "Senior level"
        assert posting.get_status_display() == "Published"
        assert posting.get_salary_period_display() == "Per month"
        assert posting.company.get_size_display() == "51-200 employees"


class TestApplications:
    def test_status_reads_as_words(self, database, posting, employee):
        applicant = Applicant(user_id=employee.id, job_id=posting.id, status=1)
        database.add(applicant)
        database.commit()
        assert applicant.get_status == "Pending"
        applicant.status = 2
        assert applicant.get_status == "Accepted"
        applicant.status = 3
        assert applicant.get_status == "Rejected"

    def test_a_candidate_applies_once(self, database, posting, employee):
        database.add(Applicant(user_id=employee.id, job_id=posting.id, status=1))
        database.commit()
        database.add(Applicant(user_id=employee.id, job_id=posting.id, status=1))
        try:
            database.commit()
        except Exception:
            database.rollback()
        else:  # pragma: no cover - the constraint is the point of the test
            raise AssertionError("a second application was accepted")
        assert len(database.scalars(select(Applicant)).all()) == 1


class TestFavorites:
    def test_removing_marks_rather_than_deletes(self, database, posting, employee):
        favorite = Favorite(user_id=employee.id, job_id=posting.id,
                            soft_deleted=False)
        database.add(favorite)
        database.commit()
        favorite.soft_deleted = True
        database.commit()
        assert len(database.scalars(select(Favorite)).all()) == 1


class TestPasswords:
    def test_round_trip(self):
        encoded = make_password("s3cret!")
        assert encoded.startswith("pbkdf2_sha256$")
        assert check_password("s3cret!", encoded)
        assert not check_password("other", encoded)

    def test_iterations_are_read_from_the_stored_value(self):
        encoded = make_password("s3cret!")
        algorithm, iterations, salt, _ = encoded.split("$")
        assert algorithm == "pbkdf2_sha256" and int(iterations) > 0 and salt
