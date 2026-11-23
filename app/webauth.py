"""Signing in, signing up, the employer and candidate areas, and the resumes.

The redirects, the refusals and the notices are the ones the site answered with
before, including where it signed a candidate back to an unprefixed path.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.db import get_session
from app.models import (
    Applicant, Category, Company, Favorite, Job, ResumeCv, ResumeCvCategory,
    ResumeCvTemplate, Tag, User,
)
from app.paging import paginate
from app.siteforms import (
    CompanyForm, EmployeeProfileForm, EmployeeRegistrationForm,
    EmployerProfileForm, EmployerRegistrationForm, JobForm, LoginForm,
)
from app.templating import add_message, render
from app.urls import reverse

router = APIRouter()
unprefixed_router = APIRouter()


def language_of(request: Request) -> str:
    return getattr(request.state, "language", settings.language_code)


def link(request: Request, name: str, *args) -> str:
    return reverse(name, *args, language=language_of(request))


def redirect(target: str, status_code: int = 302) -> RedirectResponse:
    response = RedirectResponse(target, status_code=status_code)
    response.headers["content-type"] = "text/html; charset=utf-8"
    return response


def sign_in(request: Request, user: User) -> None:
    """Record the account on the session and stamp when it last signed in."""
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    request.state.session["_auth_user_id"] = str(user.id)
    request.state.session_changed = True
    request.state.user = user


def require_login(request: Request) -> User:
    """Send an anonymous visitor to the sign-in page, remembering where they were."""
    from app import RedirectRequired

    user = getattr(request.state, "user", None)
    if user is None:
        raise RedirectRequired("%s?next=%s" % (link(request, "accounts:login"),
                                               request.url.path))
    return user


def require_role(request: Request, role: str) -> User:
    user = require_login(request)
    if user.role != role:
        raise HTTPException(status_code=403)
    return user


async def form_data(request: Request) -> dict:
    """Read a submitted form, keeping repeated names as lists."""
    raw = await request.form()
    out: dict = {}
    for key in raw.keys():
        values = raw.getlist(key)
        out[key] = values if len(values) > 1 else values[0]
    return out


# ------------------------------------------------------------------ signing ---
@router.api_route("/login/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def login(request: Request, session: Session = Depends(get_session)):
    success = request.query_params.get("next") or settings.login_redirect_url
    if getattr(request.state, "user", None) is not None:
        return redirect(success)
    form = LoginForm(session=session)
    if request.method == "POST":
        form = LoginForm(data=await form_data(request), session=session)
        if form.is_valid():
            sign_in(request, form.get_user())
            session.commit()
            return redirect(success)
    return render(request, "accounts/login.html",
                  {"form": form, "title": "Login"}, session=session)


@router.api_route("/logout/", methods=["GET", "HEAD", "OPTIONS"])
def logout(request: Request):
    request.state.session.clear()
    request.state.session_cleared = True
    request.state.session_changed = True
    request.state.user = None
    add_message(request, "success", "You are now logged out")
    return redirect("/login")


def registration(request: Request, session: Session, form_class, template: str,
                 data=None):
    if getattr(request.state, "user", None) is not None:
        return redirect(settings.login_redirect_url)
    form = form_class(data=data, session=session)
    if data is not None and form.is_valid():
        form.save()
        return redirect(link(request, "accounts:login"))
    return render(request, template, {"form": form, "title": "Register"},
                  session=session)


@router.api_route("/employee/register/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def employee_register(request: Request,
                            session: Session = Depends(get_session)):
    data = await form_data(request) if request.method == "POST" else None
    return registration(request, session, EmployeeRegistrationForm,
                        "accounts/employee/register.html", data)


@router.api_route("/employer/register/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def employer_register(request: Request,
                            session: Session = Depends(get_session)):
    data = await form_data(request) if request.method == "POST" else None
    return registration(request, session, EmployerRegistrationForm,
                        "accounts/employer/register.html", data)


@router.api_route("/employee/profile/update/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def employee_profile(request: Request,
                           session: Session = Depends(get_session)):
    user = require_role(request, "employee")
    instance = session.get(User, user.id)
    form = EmployeeProfileForm(instance=instance, session=session)
    if request.method == "POST":
        form = EmployeeProfileForm(data=await form_data(request),
                                   instance=instance, session=session)
        if form.is_valid():
            form.save()
            return redirect(link(request, "accounts:employee-profile-update"))
    return render(request, "jobs/employee/edit-profile.html",
                  {"form": form, "employee": instance}, session=session)


@router.api_route("/employer/profile/update/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def employer_profile(request: Request,
                           session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    instance = session.get(User, user.id)
    form = EmployerProfileForm(instance=instance, session=session)
    if request.method == "POST":
        form = EmployerProfileForm(data=await form_data(request),
                                   instance=instance, session=session)
        if form.is_valid():
            form.save()
            return redirect(link(request, "accounts:employer-profile-update"))
    return render(request, "jobs/employer/edit-profile.html",
                  {"form": form, "employer": instance}, session=session)


# --------------------------------------------------------------- candidate ---
@router.api_route("/apply-job/{job_id:int}/",
                  methods=["GET", "HEAD", "OPTIONS", "POST", "PUT"])
async def apply_job(job_id: int, request: Request,
                    session: Session = Depends(get_session)):
    user = require_role(request, "employee")
    if request.method != "POST":
        raise HTTPException(
            status_code=405,
            headers={"Allow": "GET, HEAD, OPTIONS, POST, PUT"})
    data = await form_data(request)
    job = session.get(Job, int(data.get("job") or 0))
    if job is None:
        return redirect(link(request, "jobs:home"))
    existing = session.scalar(
        select(Applicant).where(Applicant.user_id == user.id,
                                Applicant.job_id == job_id))
    if existing is not None:
        add_message(request, "info", "You already applied for this job")
        return redirect(link(request, "jobs:jobs-detail", job_id))
    session.add(Applicant(user_id=user.id, job_id=job.id, status=1))
    session.commit()
    add_message(request, "info", "Successfully applied for the job!")
    return redirect(link(request, "jobs:jobs-detail", job_id))


@router.api_route("/employee/my-applications", methods=["GET", "HEAD", "OPTIONS"])
def my_applications(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employee")
    statement = (
        select(Applicant)
        .where(Applicant.user_id == user.id)
        .options(selectinload(Applicant.job).selectinload(Job.company))
        .order_by(Applicant.created_at.desc())
    )
    status = request.query_params.get("status")
    if status and int(status) > 0:
        statement = statement.where(Applicant.status == int(status))
    rows = list(session.scalars(statement).all())
    page_obj, paginator, is_paginated = paginate(
        rows, 6, request.query_params.get("page"))
    return render(request, "jobs/employee/my-applications.html", {
        "applicants": page_obj.object_list, "page_obj": page_obj,
        "paginator": paginator, "is_paginated": is_paginated,
    }, session=session)


@router.api_route("/employee/favorites", methods=["GET", "HEAD", "OPTIONS"])
def favorites(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employee")
    rows = session.scalars(
        select(Favorite)
        .where(Favorite.user_id == user.id, Favorite.soft_deleted.is_(False))
        .options(selectinload(Favorite.job).selectinload(Job.company))).all()
    return render(request, "jobs/employee/favorites.html",
                  {"favorites": rows}, session=session)


# ---------------------------------------------------------------- employer ---
@router.api_route("/employer/dashboard/", methods=["GET", "HEAD", "OPTIONS"])
def dashboard(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    rows = list(session.scalars(
        select(Job).where(Job.user_id == user.id)
        .options(selectinload(Job.company), selectinload(Job.category),
                 selectinload(Job.tags), selectinload(Job.applicants))
        .order_by(Job.created_at.desc())).all())
    page_obj, paginator, is_paginated = paginate(
        rows, settings.dashboard_page_size, request.query_params.get("page"))
    companies = session.scalars(
        select(Company).where(Company.user_id == user.id)).all()
    return render(request, "jobs/employer/dashboard.html", {
        "jobs": page_obj.object_list, "companies": companies,
        "page_obj": page_obj, "paginator": paginator,
        "is_paginated": is_paginated,
    }, session=session)


@router.api_route("/employer/dashboard/all-applicants/", methods=["GET", "HEAD", "OPTIONS"])
def all_applicants(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    statement = (
        select(Applicant).join(Job, Applicant.job_id == Job.id)
        .where(Job.user_id == user.id)
        .options(selectinload(Applicant.job).selectinload(Job.company),
                 selectinload(Applicant.user))
        .order_by(Applicant.id)
    )
    status = request.query_params.get("status")
    if status:
        statement = statement.where(Applicant.status == int(status))
    rows = list(session.scalars(statement).all())
    return render(request, "jobs/employer/all-applicants.html",
                  {"applicants": rows}, session=session)


@router.api_route("/employer/dashboard/applicants/{job_id:int}/",
                  methods=["GET", "HEAD", "OPTIONS"])
def applicants_per_job(job_id: int, request: Request,
                       session: Session = Depends(get_session)):
    require_role(request, "employer")
    rows = list(session.scalars(
        select(Applicant).where(Applicant.job_id == job_id)
        .options(selectinload(Applicant.user))
        .order_by(Applicant.id)).all())
    job = session.get(Job, job_id)
    page_obj, paginator, is_paginated = paginate(
        rows, 6, request.query_params.get("page"))
    return render(request, "jobs/employer/applicants.html", {
        "applicants": page_obj.object_list, "job": job, "page_obj": page_obj,
        "paginator": paginator, "is_paginated": is_paginated,
    }, session=session)


@router.api_route(
    "/employer/dashboard/applied-applicant/{job_id:int}/view/{applicant_id:int}",
    methods=["GET", "HEAD", "OPTIONS"])
def applied_applicant(job_id: int, applicant_id: int, request: Request,
                      session: Session = Depends(get_session)):
    require_role(request, "employer")
    applicant = session.scalar(
        select(Applicant).where(Applicant.job_id == job_id,
                                Applicant.id == applicant_id)
        .options(selectinload(Applicant.job).selectinload(Job.company),
                 selectinload(Applicant.user)))
    if applicant is None:
        raise HTTPException(status_code=404)
    return render(request, "jobs/employer/applied-applicant-view.html",
                  {"applicant": applicant}, session=session)


@router.api_route("/employer/dashboard/mark-filled/{job_id:int}/",
                  methods=["GET", "HEAD", "OPTIONS"])
def mark_filled(job_id: int, request: Request,
                session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    job = session.scalar(select(Job).where(Job.user_id == user.id,
                                           Job.id == job_id))
    # A posting that is not this employer's was already a failure here.
    job.filled = True
    session.commit()
    return redirect(link(request, "jobs:employer-dashboard"))


@router.post("/employer/dashboard/send-response/{applicant_id:int}")
async def send_response(applicant_id: int, request: Request,
                        session: Session = Depends(get_session)):
    require_role(request, "employer")
    applicant = session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=404)
    data = await form_data(request)
    status = data.get("status")
    if str(applicant.status) != str(status):
        add_message(request, "success", "Response was successfully sent")
    else:
        add_message(request, "warning", "Response already sent")
    applicant.status = int(status)
    applicant.comment = data.get("comment") or ""
    session.commit()
    return redirect(link(request, "jobs:applied-applicant-view",
                         data.get("job_id"), applicant.id))


def job_page(request: Request, session: Session, template: str, title: str,
             form: JobForm, job: Job | None):
    tags = session.scalars(select(Tag)).all()
    categories = session.scalars(select(Category).order_by(Category.name)).all()
    user = request.state.user
    companies = session.scalars(
        select(Company).where(Company.user_id == user.id)).all()
    return render(request, template, {
        "form": form, "title": title, "tags": tags, "categories": categories,
        "companies": companies, "job": job,
    }, session=session)


@router.api_route("/employer/dashboard/jobs/create/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def job_create(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    form = JobForm(session=session)
    if request.method == "POST":
        form = JobForm(data=await form_data(request), session=session)
        if form.is_valid():
            form.save(user)
            return redirect(link(request, "jobs:employer-dashboard"))
    return job_page(request, session, "jobs/create.html", "Post New Job", form,
                    None)


@router.api_route("/employer/dashboard/jobs/{identifier:int}/edit/",
                  methods=["GET", "HEAD", "OPTIONS", "POST"])
async def job_edit(identifier: int, request: Request,
                   session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    job = session.scalar(select(Job).where(Job.user_id == user.id,
                                           Job.id == identifier))
    if job is None:
        raise HTTPException(status_code=404)
    form = JobForm(instance=job, session=session)
    if request.method == "POST":
        form = JobForm(data=await form_data(request), instance=job,
                       session=session)
        if form.is_valid():
            form.save(user)
            add_message(request, "success", "Job updated successfully")
            return redirect(link(request, "jobs:employer-dashboard"))
    return job_page(request, session, "jobs/update.html", "Edit Job", form, job)


@router.api_route("/employer/dashboard/company/create/", methods=["GET", "HEAD", "OPTIONS", "POST"])
async def company_create(request: Request,
                         session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    form = CompanyForm(session=session)
    if request.method == "POST":
        form = CompanyForm(data=await form_data(request), session=session)
        if form.is_valid():
            form.save(user)
            add_message(request, "success",
                        "Company profile created successfully!")
            return redirect(link(request, "jobs:employer-dashboard"))
    return render(request, "jobs/company/create.html",
                  {"form": form, "title": "Create Company Profile"},
                  session=session)


@router.api_route("/employer/dashboard/company/{identifier:int}/edit/",
                  methods=["GET", "HEAD", "OPTIONS", "POST"])
async def company_edit(identifier: int, request: Request,
                       session: Session = Depends(get_session)):
    user = require_role(request, "employer")
    company = session.scalar(select(Company).where(
        Company.user_id == user.id, Company.id == identifier))
    if company is None:
        raise HTTPException(status_code=404)
    form = CompanyForm(instance=company, session=session)
    if request.method == "POST":
        form = CompanyForm(data=await form_data(request), instance=company,
                           session=session)
        if form.is_valid():
            form.save(user)
            add_message(request, "success",
                        "Company profile updated successfully!")
            return redirect(link(request, "jobs:employer-dashboard"))
    return render(request, "jobs/company/update.html",
                  {"form": form, "company": company,
                   "title": "Edit Company Profile"}, session=session)


# ----------------------------------------------------------------- resumes ---
@router.api_route("/templates", methods=["GET", "HEAD", "OPTIONS"])
def resume_templates(request: Request, session: Session = Depends(get_session)):
    templates = session.scalars(
        select(ResumeCvTemplate).where(ResumeCvTemplate.active.is_(True))).all()
    categories = session.scalars(select(ResumeCvCategory)).all()
    return render(request, "resumes/templates.html",
                  {"templates": templates, "categories": categories},
                  session=session)


@router.post("/resume-cv/create")
async def resume_create(request: Request, session: Session = Depends(get_session)):
    user = require_role(request, "employee")
    data = await form_data(request)
    template = session.get(ResumeCvTemplate, int(data.get("template") or 0))
    if template is None or not data.get("name"):
        return redirect(link(request, "resume_cv:templates"))
    resume = ResumeCv(user_id=user.id, template_id=template.id,
                      code=uuid.uuid4().hex, name=data["name"],
                      content=data.get("content"), style=data.get("style"))
    session.add(resume)
    session.commit()
    return redirect(link(request, "resume_cv:builder",
                         str(uuid.UUID(resume.code))))


@router.api_route("/templates/builder/{code}", methods=["GET", "HEAD", "OPTIONS"])
def resume_builder(code: str, request: Request,
                   session: Session = Depends(get_session)):
    try:
        stored = uuid.UUID(code).hex
    except ValueError:
        raise HTTPException(status_code=404) from None
    resume = session.scalar(select(ResumeCv).where(ResumeCv.code == stored))
    if resume is None:
        raise HTTPException(status_code=404)
    templates = session.scalars(select(ResumeCvTemplate)).all()
    return render(request, "resumes/builder.html",
                  {"resume": resume, "templates": templates, "token": ""},
                  session=session)


@router.api_route("/resumes/", methods=["GET", "HEAD", "OPTIONS"])
def user_resumes(request: Request, session: Session = Depends(get_session)):
    user = getattr(request.state, "user", None)
    rows = session.scalars(
        select(ResumeCv).where(ResumeCv.user_id == (user.id if user else 0))
        .order_by(ResumeCv.id.desc())).all()
    return render(request, "resumes/user_resumes.html", {"resumes": rows},
                  session=session)


# ------------------------------------------------- addressed without a prefix ---
@unprefixed_router.post("/i18n/setlang/")
async def set_language(request: Request):
    """Remember the chosen language and go back where the form came from."""
    from app.middleware import language_from_path, strip_language

    data = await form_data(request)
    language = data.get("language")
    target = data.get("next") or "/"
    active = getattr(request.state, "language", settings.language_code)
    if language in settings.languages and language != active and \
            language_from_path(target) is not None:
        target = "/%s%s" % (language, strip_language(target))
    response = redirect(target)
    if language in settings.languages:
        response.set_cookie(settings.language_cookie_name, language, path="/",
                            max_age=31536000)
    return response


@unprefixed_router.api_route("/templates/load-builder/{identifier:int}",
                             methods=["GET", "HEAD", "OPTIONS"])
def load_builder(identifier: int, session: Session = Depends(get_session)):
    resume = session.get(ResumeCv, identifier)
    if resume is None:
        return JSONResponse({"error": "No template found"})
    return JSONResponse({
        "gjs-html": resume.content or resume.template.content,
        "gjs-css": resume.style or resume.template.style,
    })


@unprefixed_router.post("/templates/update-builder/{identifier:int}")
async def update_builder(identifier: int, request: Request,
                         session: Session = Depends(get_session)):
    resume = session.get(ResumeCv, identifier)
    if resume is None:
        return JSONResponse({"error": "No resume found"})
    data = json.loads(await request.body() or b"{}")
    resume.content = data.get("gjs-html")
    resume.style = data.get("gjs-css")
    session.commit()
    return JSONResponse({"success": "Updated successfully"})
