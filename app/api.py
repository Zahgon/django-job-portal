"""The JSON API.

Every endpoint keeps the status codes, the payloads, the ``Allow`` header and
the error wording the API answered with before, and refuses a method it does
not serve before it looks at who is asking.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.apicore import (
    APIError, Paginator, api_response, bearer_user, check_methods,
    not_authenticated, not_found, permission_denied, require_role, require_user,
)
from app.config import settings
from app.db import get_session
from app.forms import EMAIL_RE
from app.models import (
    Applicant, Category, Company, ExperienceLevel, Job, JobStatus, JobType,
    SalaryPeriod, Tag, User, WorkplaceType,
)
from app.security import check_password, make_password, read_token, sign_token
from app.serializers import (
    applicant_payload, applied_job_payload, category_payload,
    company_payload, company_write_payload, dashboard_job_payload, job_payload,
    tag_payload, user_payload,
)

router = APIRouter()

REQUIRED = "This field is required."
BLANK = "This field may not be blank."
DATETIME_FORMAT = (
    "Datetime has wrong format. Use one of these formats instead: "
    "YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]."
)
NO_ACCOUNT = "No active account found with the given credentials"

READ_ONLY = "GET, HEAD, OPTIONS"
WRITE_ONLY = "POST, OPTIONS"
READ_WRITE = "GET, POST, HEAD, OPTIONS"
DETAIL_WRITE = "GET, PUT, PATCH, HEAD, OPTIONS"
ANY = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class Errors(dict):
    """Field errors in the order they were found."""

    def add(self, name: str, message: str) -> None:
        self.setdefault(name, []).append(message)

    def raise_if_any(self) -> None:
        if self:
            raise APIError.fields(self)


async def payload(request: Request) -> dict:
    """The request body as a mapping; a body that is not an object is empty."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - any unreadable body is simply absent
        return {}
    return body if isinstance(body, dict) else {}


def text_field(data: dict, name: str, errors: Errors, required: bool = True,
               blank: bool = False) -> str | None:
    if name not in data:
        if required:
            errors.add(name, REQUIRED)
        return None
    value = data[name]
    value = "" if value is None else str(value)
    if not value.strip() and not blank:
        errors.add(name, BLANK if required else BLANK)
        return None
    return value


def choice_field(data: dict, name: str, choices, errors: Errors,
                 required: bool = True, default=None):
    if name not in data or data[name] in (None, ""):
        if required:
            errors.add(name, REQUIRED)
            return None
        return default
    value = str(data[name])
    if value not in [stored for stored, _ in choices]:
        errors.add(name, '"%s" is not a valid choice.' % value)
        return None
    return value


def related(session: Session, model, data: dict, name: str, errors: Errors,
            required: bool = True, owner: User | None = None):
    if name not in data or data[name] in (None, ""):
        if required:
            errors.add(name, REQUIRED)
        return None
    key = data[name]
    try:
        instance = session.get(model, int(key))
    except (TypeError, ValueError):
        instance = None
    if instance is not None and owner is not None and \
            getattr(instance, "user_id", None) != owner.id:
        instance = None
    if instance is None:
        errors.add(name, 'Invalid pk "%s" - object does not exist.' % key)
    return instance


def datetime_field(data: dict, name: str, errors: Errors, required: bool = True):
    if name not in data or data[name] in (None, ""):
        if required:
            errors.add(name, REQUIRED)
        return None
    raw = str(data[name]).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        errors.add(name, DATETIME_FORMAT)
        return None


def integer_field(data: dict, name: str, errors: Errors, default=None):
    if name not in data or data[name] in (None, ""):
        return default
    try:
        return int(data[name])
    except (TypeError, ValueError):
        errors.add(name, "A valid integer is required.")
        return None


def issue_tokens(user: User) -> dict:
    """A refresh token and an access token carrying the account's own claims."""
    now = int(time.time())
    base = {"user_id": user.id, "jti": "%s-%s" % (user.id, now),
            "user": user_payload(user)}
    access = dict(base, token_type="access",
                  exp=now + settings.access_token_lifetime, iat=now)
    refresh = dict(base, token_type="refresh",
                   exp=now + settings.refresh_token_lifetime, iat=now)
    return {"refresh": sign_token(refresh, settings.secret_key),
            "access": sign_token(access, settings.secret_key)}


# ------------------------------------------------------------------- public ---
def open_jobs(session: Session):
    return (
        select(Job).where(Job.filled.is_(False))
        .options(selectinload(Job.company), selectinload(Job.category),
                 selectinload(Job.tags), selectinload(Job.user))
        .order_by(Job.created_at.desc(), Job.id.desc())
    )


@router.api_route("/jobs/", methods=ANY)
def job_collection(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    statement = open_jobs(session)
    params = request.query_params
    if params.get("company"):
        statement = statement.where(Job.company_id == params["company"])
    category = params.get("category")
    if category:
        if category.isdigit():
            statement = statement.where(Job.category_id == int(category))
        else:
            statement = statement.join(Category).where(Category.slug == category)
    if params.get("q"):
        statement = statement.where(Job.title.ilike("%%%s%%" % params["q"]))
    if params.get("location"):
        statement = statement.where(
            Job.location.ilike("%%%s%%" % params["location"]))
    rows = [job_payload(job) for job in session.scalars(statement).all()]
    page = Paginator(request, settings.api_job_page_size).page(rows)
    return api_response(page, allow=READ_ONLY)


@router.api_route("/jobs/{identifier:int}/", methods=ANY)
def job_item(identifier: int, request: Request,
             session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    job = session.scalar(open_jobs(session).where(Job.id == identifier))
    if job is None:
        raise not_found("Job")
    return api_response(job_payload(job), allow=READ_ONLY)


def all_companies(session: Session):
    return select(Company).order_by(Company.featured.desc(),
                                    Company.created_at.desc())


@router.api_route("/companies/", methods=ANY)
def company_collection(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    statement = all_companies(session)
    params = request.query_params
    if params.get("q"):
        statement = statement.where(Company.name.ilike("%%%s%%" % params["q"]))
    if params.get("industry"):
        statement = statement.where(
            Company.industry.ilike("%%%s%%" % params["industry"]))
    if params.get("featured") in ("1", "true", "True"):
        statement = statement.where(Company.featured.is_(True))
    rows = [company_payload(c) for c in session.scalars(statement).all()]
    page = Paginator(request, settings.api_company_page_size).page(rows)
    return api_response(page, allow=READ_ONLY)


@router.api_route("/companies/{identifier:int}/", methods=ANY)
def company_item(identifier: int, request: Request,
                 session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    company = session.get(Company, identifier)
    if company is None:
        raise not_found("Company")
    return api_response(company_payload(company), allow=READ_ONLY)


@router.api_route("/search/", methods=ANY)
def search(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    statement = open_jobs(session)
    params = request.query_params
    if params.get("location"):
        statement = statement.where(
            Job.location.ilike("%%%s%%" % params["location"]))
    if params.get("position"):
        statement = statement.where(
            Job.title.ilike("%%%s%%" % params["position"]))
    category = params.get("category")
    if category:
        if category.isdigit():
            statement = statement.where(Job.category_id == int(category))
        else:
            statement = statement.join(Category).where(Category.slug == category)
    return api_response([job_payload(j) for j in session.scalars(statement).all()],
                        allow=READ_ONLY)


@router.api_route("/categories/", methods=ANY)
def categories(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    rows = session.scalars(select(Category).order_by(Category.id)).all()
    return api_response([category_payload(c) for c in rows], allow=READ_ONLY)


@router.api_route("/tags/", methods=ANY)
def tags(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    rows = session.scalars(select(Tag).order_by(Tag.id)).all()
    return api_response([tag_payload(t) for t in rows], allow=READ_ONLY)


# --------------------------------------------------------------- accounts ---
@router.api_route("/register/", methods=ANY)
async def register(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("POST",), WRITE_ONLY)
    data = await payload(request)
    errors = Errors()
    email = text_field(data, "email", errors)
    password = text_field(data, "password", errors)
    password2 = text_field(data, "password2", errors)
    role = text_field(data, "role", errors)
    gender = data.get("gender") or ""
    if email and not EMAIL_RE.match(email):
        errors.add("email", "Enter a valid email address.")
    elif email and session.scalar(select(User).where(User.email == email)):
        errors.add("email", "A user with that email already exists.")
    if password and password2 and password != password2:
        errors.add("password2", "Password fields didn't match.")
    errors.raise_if_any()
    user = User(email=email, gender=gender, role=role,
                password=make_password(password), is_active=True,
                is_staff=False, is_superuser=False, first_name="", last_name="")
    session.add(user)
    session.commit()
    return api_response({"status": True, "message": "Successfully registered"},
                        status_code=201, allow=WRITE_ONLY)


@router.api_route("/login/", methods=ANY)
async def login(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("POST",), WRITE_ONLY)
    data = await payload(request)
    errors = Errors()
    email = text_field(data, "email", errors)
    password = text_field(data, "password", errors)
    errors.raise_if_any()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or \
            not check_password(password, user.password):
        raise APIError.detail(401, NO_ACCOUNT)
    return api_response(issue_tokens(user), allow=WRITE_ONLY)


@router.api_route("/token/refresh/", methods=ANY)
async def refresh_token(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("POST",), WRITE_ONLY)
    data = await payload(request)
    errors = Errors()
    token = text_field(data, "refresh", errors)
    errors.raise_if_any()
    try:
        claims = read_token(token, settings.secret_key)
    except Exception:  # noqa: BLE001 - any unreadable token is simply not valid
        raise APIError(401, [{"detail": "Token is invalid or expired"},
                             {"code": "token_not_valid"}],
                       "Token is invalid or expired") from None
    user = session.get(User, int(claims.get("user_id", 0)))
    if user is None:
        raise APIError(401, [{"detail": "Token is invalid or expired"},
                             {"code": "token_not_valid"}],
                       "Token is invalid or expired")
    return api_response(issue_tokens(user), allow=WRITE_ONLY)


@router.api_route("/employee/profile/", methods=ANY)
async def employee_profile(request: Request,
                           session: Session = Depends(get_session)):
    check_methods(request, ("GET", "PUT"), "GET, PUT")
    user = require_role(request, session, "employee")
    if request.method == "PUT":
        data = await payload(request)
        for name in ("first_name", "last_name", "gender", "role"):
            if name in data and data[name] is not None:
                setattr(user, name, str(data[name]))
        session.commit()
    return api_response(user_payload(user), allow="GET, PUT")


# -------------------------------------------------------------- candidate ---
@router.api_route("/apply-job/{job_id:int}/", methods=ANY)
async def apply_job(job_id: int, request: Request,
                    session: Session = Depends(get_session)):
    check_methods(request, ("POST",), "POST")
    user = require_role(request, session, "employee")
    data = await payload(request)
    errors = Errors()
    job = related(session, Job, data, "job", errors)
    errors.raise_if_any()
    existing = session.scalar(
        select(Applicant).where(Applicant.user_id == user.id,
                                Applicant.job_id == job.id))
    if existing is not None:
        raise APIError(400,
                       [{"non_field_errors": "You have already applied to this job"}],
                       "You have already applied to this job ")
    applicant = Applicant(user_id=user.id, job_id=job.id, status=1)
    session.add(applicant)
    session.commit()
    return api_response({"job": job.id}, status_code=201, allow="POST")


@router.api_route("/applied-jobs/", methods=ANY)
def applied_jobs(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    user = require_role(request, session, "employee")
    rows = session.scalars(
        select(Applicant).where(Applicant.user_id == user.id)
        .options(selectinload(Applicant.job))).all()
    by_job = {applicant.job_id: applicant for applicant in rows}
    jobs = session.scalars(
        select(Job).where(Job.id.in_(list(by_job)))
        .options(selectinload(Job.company), selectinload(Job.category),
                 selectinload(Job.tags), selectinload(Job.user))
        .order_by(Job.created_at.desc(), Job.id.desc())).all()
    out = [applied_job_payload(job, by_job[job.id]) for job in jobs]
    return api_response(out, allow=READ_ONLY)


@router.api_route("/applied-for-job/{job_id:int}/", methods=ANY)
def applied_for_job(job_id: int, request: Request,
                    session: Session = Depends(get_session)):
    check_methods(request, ("GET",), "GET, OPTIONS")
    user = require_role(request, session, "employee")
    applied = session.scalar(
        select(Applicant).where(Applicant.user_id == user.id,
                                Applicant.job_id == job_id)) is not None
    return api_response({"is_applied": applied}, allow="GET, OPTIONS")


# --------------------------------------------------------------- employer ---
@router.api_route("/employer/dashboard/", methods=ANY)
def employer_dashboard(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    user = require_role(request, session, "employer")
    rows = session.scalars(
        select(Job).where(Job.user_id == user.id)
        .options(selectinload(Job.company), selectinload(Job.category),
                 selectinload(Job.tags), selectinload(Job.user),
                 selectinload(Job.applicants))
        .order_by(Job.created_at.desc(), Job.id.desc())).all()
    return api_response([dashboard_job_payload(job) for job in rows],
                        allow=READ_ONLY)


@router.api_route("/employer/jobs/create/", methods=ANY)
async def employer_job_create(request: Request,
                              session: Session = Depends(get_session)):
    check_methods(request, ("POST",), WRITE_ONLY)
    user = require_role(request, session, "employer")
    data = await payload(request)
    errors = Errors()
    company = related(session, Company, data, "company", errors, owner=user)
    category = related(session, Category, data, "category", errors)
    title = text_field(data, "title", errors)
    description = text_field(data, "description", errors)
    location = text_field(data, "location", errors)
    kind = choice_field(data, "type", JobType.CHOICES, errors)
    deadline = datetime_field(data, "application_deadline", errors)
    workplace = choice_field(data, "workplace_type", WorkplaceType.CHOICES,
                             errors, required=False,
                             default=WorkplaceType.ON_SITE)
    level = choice_field(data, "experience_level", ExperienceLevel.CHOICES,
                         errors, required=False, default=ExperienceLevel.ENTRY)
    status = choice_field(data, "status", JobStatus.CHOICES, errors,
                          required=False, default=JobStatus.PUBLISHED)
    period = choice_field(data, "salary_period", SalaryPeriod.CHOICES, errors,
                          required=False, default=SalaryPeriod.MONTH)
    tag_ids = data.get("tags")
    tags_chosen = []
    if tag_ids is None:
        errors.add("tags", REQUIRED)
    else:
        for key in tag_ids if isinstance(tag_ids, list) else [tag_ids]:
            tag = session.get(Tag, int(key)) if str(key).isdigit() else None
            if tag is None:
                errors.add("tags",
                           'Invalid pk "%s" - object does not exist.' % key)
            else:
                tags_chosen.append(tag)
    errors.raise_if_any()
    job = Job(
        user_id=user.id, company_id=company.id, category_id=category.id,
        title=title, description=description,
        responsibilities=data.get("responsibilities") or "",
        requirements=data.get("requirements") or "", location=location,
        type=kind, workplace_type=workplace, experience_level=level,
        application_deadline=deadline.replace(tzinfo=None),
        website=data.get("website"), filled=False, status=status,
        salary=integer_field(data, "salary", errors, 0) or 0,
        salary_currency=str(data.get("salary_currency") or "BDT"),
        salary_period=period,
        vacancy=integer_field(data, "vacancy", errors, 1) or 1,
        is_featured=bool(data.get("is_featured")),
    )
    job.ensure_slug()
    session.add(job)
    session.flush()
    for tag in tags_chosen:
        job.tags.append(tag)
    session.commit()
    return api_response(job_payload(job), status_code=201, allow=WRITE_ONLY)


@router.api_route("/employer/companies/", methods=ANY)
async def employer_companies(request: Request,
                             session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD", "POST"), READ_WRITE)
    user = require_role(request, session, "employer")
    if request.method == "POST":
        data = await payload(request)
        errors = Errors()
        name = text_field(data, "name", errors)
        errors.raise_if_any()
        company = Company(user_id=user.id, name=name,
                          description=data.get("description"),
                          website=data.get("website"), logo=data.get("logo") or "",
                          industry=data.get("industry"),
                          size=str(data.get("size") or ""),
                          culture_benefits=data.get("culture_benefits"),
                          tagline=data.get("tagline"),
                          headquarters=data.get("headquarters"),
                          linkedin_url=data.get("linkedin_url"),
                          facebook_url=data.get("facebook_url"),
                          cover_image=data.get("cover_image") or "")
        company.ensure_slug()
        session.add(company)
        session.commit()
        return api_response(company_write_payload(company), status_code=201,
                            allow=READ_WRITE)
    rows = session.scalars(
        select(Company).where(Company.user_id == user.id)
        .order_by(Company.created_at.desc())).all()
    return api_response([company_payload(c) for c in rows], allow=READ_WRITE)


@router.api_route("/employer/companies/{identifier:int}/", methods=ANY)
async def employer_company(identifier: int, request: Request,
                           session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD", "PUT", "PATCH"), DETAIL_WRITE)
    user = require_role(request, session, "employer")
    company = session.scalar(select(Company).where(
        Company.id == identifier, Company.user_id == user.id))
    if company is None:
        raise not_found("Company")
    if request.method in ("PUT", "PATCH"):
        data = await payload(request)
        if request.method == "PUT":
            errors = Errors()
            text_field(data, "name", errors)
            errors.raise_if_any()
        for name in ("name", "description", "website", "logo", "industry",
                     "size", "culture_benefits", "tagline", "headquarters",
                     "linkedin_url", "facebook_url", "cover_image"):
            if name in data:
                setattr(company, name, data[name])
        session.commit()
        return api_response(company_write_payload(company), allow=DETAIL_WRITE)
    return api_response(company_payload(company), allow=DETAIL_WRITE)


@router.api_route("/employer/applicants/", methods=ANY)
def employer_applicants(request: Request, session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    user = require_role(request, session, "employer")
    rows = session.scalars(
        select(Applicant).join(Job, Applicant.job_id == Job.id)
        .where(Job.user_id == user.id)
        .options(selectinload(Applicant.user),
                 selectinload(Applicant.job).selectinload(Job.company),
                 selectinload(Applicant.job).selectinload(Job.category),
                 selectinload(Applicant.job).selectinload(Job.tags),
                 selectinload(Applicant.job).selectinload(Job.user))
        .order_by(Applicant.id)).all()
    return api_response([applicant_payload(a) for a in rows], allow=READ_ONLY)


@router.api_route("/employer/applicants/{job_id:int}/", methods=ANY)
def employer_applicants_for_job(job_id: int, request: Request,
                                session: Session = Depends(get_session)):
    check_methods(request, ("GET", "HEAD"), READ_ONLY)
    user = require_role(request, session, "employer")
    owns = session.scalar(select(Job).where(Job.id == job_id,
                                            Job.user_id == user.id))
    if owns is None:
        raise permission_denied()
    rows = session.scalars(
        select(Applicant).where(Applicant.job_id == job_id)
        .options(selectinload(Applicant.user),
                 selectinload(Applicant.job).selectinload(Job.company),
                 selectinload(Applicant.job).selectinload(Job.category),
                 selectinload(Applicant.job).selectinload(Job.tags),
                 selectinload(Applicant.job).selectinload(Job.user))
        .order_by(Applicant.id)).all()
    return api_response([applicant_payload(a) for a in rows], allow=READ_ONLY)


@router.api_route(
    "/employer/applicants/{applicant_id:int}/{status_code:int}/update/",
    methods=ANY)
async def update_applicant_status(applicant_id: int, status_code: int,
                                  request: Request,
                                  session: Session = Depends(get_session)):
    check_methods(request, ("POST",), WRITE_ONLY)
    user = require_role(request, session, "employer")
    applicant = session.scalar(
        select(Applicant).where(Applicant.id == applicant_id)
        .options(selectinload(Applicant.job)))
    if applicant is None:
        return api_response({"message": "Applicant not found"}, status_code=404,
                            allow=WRITE_ONLY)
    if applicant.job.user_id != user.id:
        return api_response({"errors": "You are not authorized"},
                            status_code=403, allow=WRITE_ONLY)
    applicant.status = status_code if status_code in (1, 2) else 3
    data = await payload(request)
    applicant.comment = data.get("comment", "")
    session.commit()
    return api_response({"message": "Applicant status updated"},
                        allow=WRITE_ONLY)
