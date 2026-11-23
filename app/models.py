"""The persistence layer.

Every table, column, index and constraint keeps the name and shape the deployed
database already has, so the schema the migrations build is the schema that was
there before and no data has to move.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CHAR, Column, DateTime, ForeignKey, Index, Integer,
    Numeric, SmallInteger, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base
from app.text import slugify


def utcnow() -> datetime:
    """The default timestamp for rows that record when they were created."""
    return datetime.now(timezone.utc)


class JobType:
    FULL_TIME = "1"
    PART_TIME = "2"
    INTERNSHIP = "3"
    CHOICES = ((FULL_TIME, "Full time"), (PART_TIME, "Part time"),
               (INTERNSHIP, "Internship"))


class CompanySize:
    CHOICES = (("1", "1-10 employees"), ("2", "11-50 employees"),
               ("3", "51-200 employees"), ("4", "201-500 employees"),
               ("5", "501-1000 employees"), ("6", "1000+ employees"))


class WorkplaceType:
    ON_SITE = "on_site"
    CHOICES = (("on_site", "On-site"), ("remote", "Remote"), ("hybrid", "Hybrid"))


class ExperienceLevel:
    ENTRY = "entry"
    CHOICES = (("entry", "Entry level"), ("mid", "Mid level"),
               ("senior", "Senior level"), ("lead", "Lead/Staff"))


class SalaryPeriod:
    MONTH = "month"
    CHOICES = (("month", "Per month"), ("year", "Per year"), ("hour", "Per hour"))


class JobStatus:
    PUBLISHED = "published"
    CHOICES = (("draft", "Draft"), ("published", "Published"), ("closed", "Closed"))


GENDER_CHOICES = (("male", "Male"), ("female", "Female"))


def display(choices, value):
    """The label a choice field shows, or the raw value when it is not a choice."""
    for stored, label in choices:
        if stored == value:
            return label
    return value


class User(Base):
    """An account; the e-mail address is the identifier people sign in with."""

    __tablename__ = "accounts_user"

    id = Column(Integer, primary_key=True)
    password = Column(String(128), nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    first_name = Column(String(150), nullable=False, default="")
    last_name = Column(String(150), nullable=False, default="")
    is_staff = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    date_joined = Column(DateTime, nullable=False, default=utcnow)
    role = Column(String(12), nullable=False)
    gender = Column(String(10), nullable=True, default="")
    email = Column(String(254), nullable=False, unique=True)

    companies = relationship("Company", back_populates="user")
    posted_jobs = relationship("Job", back_populates="user")

    @property
    def is_authenticated(self) -> bool:
        return True

    def get_full_name(self) -> str:
        return ("%s %s" % (self.first_name or "", self.last_name or "")).strip()

    def get_username(self) -> str:
        return self.email

    def get_gender_display(self) -> str:
        return display(GENDER_CHOICES, self.gender)

    def __str__(self) -> str:
        return self.email


class Category(Base):
    """A job category; the slug is derived from the name when none is given."""

    __tablename__ = "categories_category"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=False)

    jobs = relationship("Job", back_populates="category")

    def ensure_slug(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)

    def __str__(self) -> str:
        return self.name


class Tag(Base):
    """A free-form label a job can carry."""

    __tablename__ = "tags_tag"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

    def __str__(self) -> str:
        return self.name


job_tags = Table(
    "jobsapp_job_tags",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", Integer, ForeignKey("jobsapp_job.id"), nullable=False,
           index=True),
    Column("tag_id", Integer, ForeignKey("tags_tag.id"), nullable=False,
           index=True),
    UniqueConstraint("job_id", "tag_id", name="jobsapp_job_tags_job_id_tag_id_uniq"),
)


class Company(Base):
    """An employer profile; one owner may not register the same name twice."""

    __tablename__ = "jobsapp_company"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uniq_company_name_per_owner"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), nullable=False,
                     index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(140), nullable=False, unique=True)
    tagline = Column(String(160), nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String(200), nullable=True)
    logo = Column(String(100), nullable=True, default="")
    industry = Column(String(100), nullable=True)
    headquarters = Column(String(150), nullable=True)
    size = Column(String(20), nullable=False, default="")
    culture_benefits = Column(Text, nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    featured = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    linkedin_url = Column(String(200), nullable=True)
    facebook_url = Column(String(200), nullable=True)
    cover_image = Column(String(100), nullable=True, default="")

    user = relationship("User", back_populates="companies")
    jobs = relationship("Job", back_populates="company")

    def ensure_slug(self) -> None:
        if not self.slug:
            self.slug = slugify("%s-%s" % (self.name, self.user_id))

    def get_size_display(self) -> str:
        return display(CompanySize.CHOICES, self.size)

    def __str__(self) -> str:
        return self.name


class Job(Base):
    """A posting; it belongs to a company and to the employer who wrote it."""

    __tablename__ = "jobsapp_job"
    __table_args__ = (
        Index("jobsapp_job_status_88565f_idx", "status", "filled"),
        Index("jobsapp_job_type_b00a27_idx", "type", "workplace_type"),
        Index("jobsapp_job_categor_e9323e_idx", "category_id"),
        Index("jobsapp_job_created_bcca72_idx", "created_at"),
        Index("jobsapp_job_applica_564e1a_idx", "application_deadline"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), nullable=False,
                     index=True)
    company_id = Column(Integer, ForeignKey("jobsapp_company.id"), nullable=False,
                        index=True)
    # The category arrived in a later migration, so its key is a big integer.
    category_id = Column(BigInteger, ForeignKey("categories_category.id"),
                         nullable=True, index=True)
    title = Column(String(300), nullable=False)
    slug = Column(String(340), nullable=False, index=True)
    description = Column(Text, nullable=False)
    responsibilities = Column(Text, nullable=False, default="")
    requirements = Column(Text, nullable=False, default="")
    location = Column(String(200), nullable=False)
    type = Column(String(10), nullable=False)
    workplace_type = Column(String(20), nullable=False,
                            default=WorkplaceType.ON_SITE)
    experience_level = Column(String(20), nullable=False,
                              default=ExperienceLevel.ENTRY)
    application_deadline = Column(DateTime, nullable=False)
    website = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    filled = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default=JobStatus.PUBLISHED)
    salary = Column(Integer, nullable=False, default=0)
    salary_min = Column(Numeric(10, 2), nullable=True)
    salary_max = Column(Numeric(10, 2), nullable=True)
    salary_currency = Column(String(5), nullable=False, default="BDT")
    salary_period = Column(String(10), nullable=False, default=SalaryPeriod.MONTH)
    vacancy = Column(Integer, nullable=False, default=1)
    is_featured = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="posted_jobs")
    company = relationship("Company", back_populates="jobs")
    category = relationship("Category", back_populates="jobs")
    tags = relationship("Tag", secondary=job_tags, order_by="Tag.id")
    applicants = relationship("Applicant", back_populates="job")
    favorites = relationship("Favorite", back_populates="job")

    def ensure_slug(self) -> None:
        if not self.slug:
            self.slug = slugify("%s-%s-%s" % (self.title, self.company_id,
                                              self.user_id))

    def get_type_display(self) -> str:
        return display(JobType.CHOICES, self.type)

    def get_workplace_type_display(self) -> str:
        return display(WorkplaceType.CHOICES, self.workplace_type)

    def get_experience_level_display(self) -> str:
        return display(ExperienceLevel.CHOICES, self.experience_level)

    def get_status_display(self) -> str:
        return display(JobStatus.CHOICES, self.status)

    def get_salary_period_display(self) -> str:
        return display(SalaryPeriod.CHOICES, self.salary_period)

    def __str__(self) -> str:
        return self.title


class Applicant(Base):
    """One application; a candidate may apply to a posting only once."""

    __tablename__ = "jobsapp_applicant"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="jobsapp_applicant_user_id_job_id_uniq"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), nullable=False,
                     index=True)
    job_id = Column(Integer, ForeignKey("jobsapp_job.id"), nullable=False,
                    index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    comment = Column(Text, nullable=True)
    status = Column(SmallInteger, nullable=False, default=1)

    user = relationship("User")
    job = relationship("Job", back_populates="applicants")

    @property
    def get_status(self) -> str:
        if self.status == 1:
            return "Pending"
        if self.status == 2:
            return "Accepted"
        return "Rejected"

    def __str__(self) -> str:
        return self.user.get_full_name() if self.user else ""


class Favorite(Base):
    """A saved posting; removing one marks it rather than deleting the row."""

    __tablename__ = "jobsapp_favorite"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), nullable=False,
                     index=True)
    job_id = Column(Integer, ForeignKey("jobsapp_job.id"), nullable=False,
                    index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    soft_deleted = Column(Boolean, nullable=False, default=False)

    user = relationship("User")
    job = relationship("Job", back_populates="favorites")

    def __str__(self) -> str:
        return self.job.title if self.job else ""


class ResumeCvCategory(Base):
    """A family of resume templates."""

    __tablename__ = "resume_cv_resumecvcategory"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    thumbnail = Column(String(100), nullable=True)
    color = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    templates = relationship("ResumeCvTemplate", back_populates="category")

    def __str__(self) -> str:
        return self.name


class ResumeCvTemplate(Base):
    """A resume template a candidate can start from."""

    __tablename__ = "resume_cv_resumecvtemplate"

    id = Column(Integer, primary_key=True)
    # The resume tables were created with wide keys, so theirs are big integers.
    category_id = Column(BigInteger, ForeignKey("resume_cv_resumecvcategory.id"),
                         nullable=False, index=True)
    name = Column(String(255), nullable=False)
    thumbnail = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    style = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=False)
    is_premium = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    category = relationship("ResumeCvCategory", back_populates="templates")
    resume_cvs = relationship("ResumeCv", back_populates="template")

    def __str__(self) -> str:
        return self.name


class ResumeCv(Base):
    """A candidate's resume, edited in the builder and addressed by its code."""

    __tablename__ = "resume_cv_resumecv"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), nullable=False,
                     index=True)
    template_id = Column(BigInteger, ForeignKey("resume_cv_resumecvtemplate.id"),
                         nullable=False, index=True)
    code = Column(CHAR(32), nullable=False, default=lambda: uuid.uuid4().hex)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    style = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=True)
    view_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = relationship("User")
    template = relationship("ResumeCvTemplate", back_populates="resume_cvs")

    def __str__(self) -> str:
        return self.name
