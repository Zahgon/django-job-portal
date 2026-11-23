"""The pages people browse.

Each route answers with the page, the redirect or the status the site already
answered with, including the ones that were wrong before.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.db import get_session
from app.models import (
    Applicant, Category, Company, Favorite, Job, User,
)
from app.paging import paginate
from app.templating import render
from app.urls import reverse

router = APIRouter()


def language_of(request: Request) -> str:
    return getattr(request.state, "language", settings.language_code)


def link(request: Request, name: str, *args) -> str:
    return reverse(name, *args, language=language_of(request))


def unfilled(session: Session):
    """The postings that are still open, newest first, as the site lists them."""
    return (
        select(Job)
        .where(Job.filled.is_(False))
        .options(selectinload(Job.company), selectinload(Job.category),
                 selectinload(Job.tags), selectinload(Job.user))
        .order_by(Job.created_at.desc(), Job.id.desc())
    )


@router.api_route("/", methods=["GET", "HEAD", "OPTIONS"])
def home(request: Request, session: Session = Depends(get_session)):
    jobs = session.scalars(unfilled(session).limit(6)).all()
    month = datetime.now(timezone.utc).month
    trendings = [
        job for job in session.scalars(unfilled(session)).all()
        if job.created_at.month == month
    ][:3]
    live_jobs_count = session.scalar(
        select(func.count()).select_from(Job).where(Job.filled.is_(False)))
    companies_count = session.scalar(select(func.count()).select_from(Company))
    candidates_count = session.scalar(
        select(func.count()).select_from(User).where(User.role == "employee"))
    new_jobs_count = len([
        job for job in session.scalars(unfilled(session)).all()
        if job.created_at.month == month
    ])
    return render(request, "home.html", {
        "jobs": jobs,
        "trendings": trendings,
        "live_jobs_count": live_jobs_count,
        "companies_count": companies_count,
        "candidates_count": candidates_count,
        "new_jobs_count": new_jobs_count,
    }, session=session)


@router.api_route("/about-us/", methods=["GET", "HEAD", "OPTIONS"])
def about_us(request: Request, session: Session = Depends(get_session)):
    return render(request, "about_us.html", {}, session=session)


@router.api_route("/search/", methods=["GET", "HEAD", "OPTIONS"])
def search(request: Request, session: Session = Depends(get_session)):
    statement = unfilled(session)
    location = request.query_params.get("location", "")
    position = request.query_params.get("position", "")
    category = request.query_params.get("category", "")
    if location:
        statement = statement.where(Job.location.ilike("%%%s%%" % location))
    if position:
        statement = statement.where(Job.title.ilike("%%%s%%" % position))
    if category:
        statement = statement.where(Job.category_id == category)
    jobs = session.scalars(statement).all()
    categories = session.scalars(
        select(Category).order_by(Category.name)).all()
    return render(request, "jobs/search.html",
                  {"jobs": jobs, "categories": categories}, session=session)


@router.api_route("/jobs/", methods=["GET", "HEAD", "OPTIONS"])
def job_list(request: Request, session: Session = Depends(get_session)):
    statement = unfilled(session)
    category = request.query_params.get("category")
    if category:
        statement = statement.where(Job.category_id == category)
    rows = list(session.scalars(statement).all())
    page_obj, paginator, is_paginated = paginate(
        rows, settings.jobs_page_size, request.query_params.get("page"))
    categories = session.scalars(select(Category).order_by(Category.name)).all()
    return render(request, "jobs/jobs.html", {
        "jobs": page_obj.object_list,
        "total_jobs": len(rows),
        "categories": categories,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": is_paginated,
    }, session=session)


@router.api_route("/jobs/{identifier:int}/", methods=["GET", "HEAD", "OPTIONS"])
def job_detail(identifier: int, request: Request,
               session: Session = Depends(get_session)):
    job = session.get(Job, identifier)
    if job is None:
        raise HTTPException(status_code=404)
    return render(request, "jobs/details.html", {"job": job}, session=session)


@router.api_route("/companies/", methods=["GET", "HEAD", "OPTIONS"])
def company_list(request: Request, session: Session = Depends(get_session)):
    statement = select(Company).order_by(Company.featured.desc(),
                                         Company.created_at.desc())
    industry = request.query_params.get("industry", "")
    if industry:
        statement = statement.where(Company.industry.ilike("%%%s%%" % industry))
    rows = list(session.scalars(statement).all())
    page_obj, paginator, is_paginated = paginate(
        rows, 12, request.query_params.get("page"))
    return render(request, "jobs/company/list.html", {
        "companies": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": is_paginated,
    }, session=session)


@router.api_route("/companies/featured/", methods=["GET", "HEAD", "OPTIONS"])
def company_featured(request: Request, session: Session = Depends(get_session)):
    rows = list(session.scalars(
        select(Company).where(Company.featured.is_(True))
        .order_by(Company.featured.desc(), Company.created_at.desc())).all())
    page_obj, paginator, is_paginated = paginate(
        rows, 12, request.query_params.get("page"))
    return render(request, "jobs/company/featured.html", {
        "companies": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": is_paginated,
    }, session=session)


@router.api_route("/companies/{identifier:int}/", methods=["GET", "HEAD", "OPTIONS"])
def company_detail(identifier: int, request: Request,
                   session: Session = Depends(get_session)):
    company = session.get(Company, identifier)
    if company is None:
        raise HTTPException(status_code=404)
    jobs = session.scalars(
        select(Job).where(Job.company_id == company.id, Job.filled.is_(False))
        .order_by(Job.created_at.desc())).all()
    return render(request, "jobs/company/detail.html", {
        "company": company, "jobs": jobs, "total_jobs": len(jobs),
    }, session=session)


@router.post("/favorite/")
async def favorite(request: Request, session: Session = Depends(get_session)):
    """Saving and unsaving a posting; unsaving marks the row rather than removing it."""
    user = getattr(request.state, "user", None)
    if user is None:
        return JSONResponse({"auth": False, "status": "error"})
    form = await request.form()
    job_id = form.get("job_id")
    existing = session.scalar(
        select(Favorite).where(Favorite.job_id == job_id,
                               Favorite.user_id == user.id,
                               Favorite.soft_deleted.is_(False)))
    if existing is not None:
        existing.soft_deleted = True
        session.commit()
        return JSONResponse({"auth": True, "status": "removed",
                             "message": "Job removed from your favorite list"})
    session.add(Favorite(job_id=int(job_id), user_id=user.id,
                         soft_deleted=False))
    session.commit()
    return JSONResponse({"auth": True, "status": "added",
                         "message": "Job added to your favorite list"})
