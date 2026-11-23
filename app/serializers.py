"""How rows are written out as JSON.

The payload of every endpoint keeps the keys, the nesting and the empty-value
conventions the API already answered with: an unset upload reads as ``null``,
a choice field is accompanied by the label it displays under, and related rows
are written out in full rather than as identifiers.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models import (
    Applicant, Category, Company, CompanySize, ExperienceLevel, Job, JobStatus,
    JobType, SalaryPeriod, Tag, User, WorkplaceType, display,
)


def isoformat(value) -> str | None:
    """Timestamps are written in UTC with a trailing Z, as they were before."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        text = value.astimezone(timezone.utc).isoformat()
        return text.replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def upload(value) -> str | None:
    """An upload field reads as null when nothing was uploaded."""
    return value or None


def number(value) -> str | None:
    """A fixed-point column is written out as a string, as it was before."""
    if value is None:
        return None
    return str(Decimal(value))


def user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "gender": user.gender,
        "email": user.email,
        "date_joined": isoformat(user.date_joined),
    }


def category_payload(category: Category | None) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
    }


def tag_payload(tag: Tag) -> dict:
    return {"id": tag.id, "name": tag.name}


def company_payload(company: Company) -> dict:
    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "tagline": company.tagline,
        "description": company.description,
        "website": company.website,
        "logo": upload(company.logo),
        "industry": company.industry,
        "headquarters": company.headquarters,
        "size": company.size,
        "size_display": company.get_size_display(),
        "culture_benefits": company.culture_benefits,
        "is_verified": company.is_verified,
        "featured": company.featured,
        "linkedin_url": company.linkedin_url,
        "facebook_url": company.facebook_url,
        "cover_image": upload(company.cover_image),
        "created_at": isoformat(company.created_at),
        "updated_at": isoformat(company.updated_at),
    }


def company_write_payload(company: Company) -> dict:
    """What a write to the employer's own company answers with."""
    return {
        "id": company.id,
        "name": company.name,
        "description": company.description,
        "website": company.website,
        "logo": upload(company.logo),
        "industry": company.industry,
        "size": company.size,
        "culture_benefits": company.culture_benefits,
        "tagline": company.tagline,
        "headquarters": company.headquarters,
        "linkedin_url": company.linkedin_url,
        "facebook_url": company.facebook_url,
        "cover_image": upload(company.cover_image),
    }


def job_payload(job: Job) -> dict:
    return {
        "id": job.id,
        "user": user_payload(job.user),
        "company": company_payload(job.company),
        "category": category_payload(job.category),
        "job_tags": [tag_payload(tag) for tag in job.tags],
        "type_display": display(JobType.CHOICES, job.type),
        "workplace_type_display": display(WorkplaceType.CHOICES, job.workplace_type),
        "experience_level_display": display(ExperienceLevel.CHOICES,
                                            job.experience_level),
        "status_display": display(JobStatus.CHOICES, job.status),
        "salary_period_display": display(SalaryPeriod.CHOICES, job.salary_period),
        "title": job.title,
        "slug": job.slug,
        "description": job.description,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
        "location": job.location,
        "type": job.type,
        "workplace_type": job.workplace_type,
        "experience_level": job.experience_level,
        "application_deadline": isoformat(job.application_deadline),
        "website": job.website,
        "created_at": isoformat(job.created_at),
        "updated_at": isoformat(job.updated_at),
        "filled": job.filled,
        "status": job.status,
        "salary": job.salary,
        "salary_min": number(job.salary_min),
        "salary_max": number(job.salary_max),
        "salary_currency": job.salary_currency,
        "salary_period": job.salary_period,
        "vacancy": job.vacancy,
        "is_featured": job.is_featured,
        "tags": [tag.id for tag in job.tags],
    }


def dashboard_job_payload(job: Job) -> dict:
    payload = job_payload(job)
    payload["total_candidates"] = len(job.applicants)
    return payload


def applicant_payload(applicant: Applicant) -> dict:
    return {
        "id": applicant.id,
        "job_id": applicant.job_id,
        "applied_user": user_payload(applicant.user),
        "job": job_payload(applicant.job),
        "status": applicant.get_status,
        "created_at": isoformat(applicant.created_at),
        "comment": applicant.comment,
    }


def applied_job_payload(job: Job, applicant: Applicant) -> dict:
    """A posting as the candidate's own list shows it, with their application."""
    payload = job_payload(job)
    for key in ("job_tags", "type_display", "workplace_type_display",
                "experience_level_display", "status_display",
                "salary_period_display"):
        payload.pop(key, None)
    payload["applicant"] = applicant_payload(applicant)
    return payload
