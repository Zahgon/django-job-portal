"""Named routes.

Pages address one another by name, as they did before, so a path can change in
one place. Names that belong to the translated part of the site are built with
the language prefix of the request that asks for them.
"""
from __future__ import annotations

from app.config import settings

# name -> (path template, carries a language prefix)
ROUTES: dict[str, tuple[str, bool]] = {
    "jobs:home": ("/", True),
    "jobs:favorite": ("/favorite/", True),
    "jobs:search": ("/search/", True),
    "jobs:jobs": ("/jobs/", True),
    "jobs:jobs-detail": ("/jobs/{0}/", True),
    "jobs:about-us": ("/about-us/", True),
    "jobs:apply-job": ("/apply-job/{0}/", True),
    "jobs:company-list": ("/companies/", True),
    "jobs:company-featured": ("/companies/featured/", True),
    "jobs:company-detail": ("/companies/{0}/", True),
    "jobs:employer-dashboard": ("/employer/dashboard/", True),
    "jobs:employer-all-applicants": ("/employer/dashboard/all-applicants/", True),
    "jobs:employer-dashboard-applicants":
        ("/employer/dashboard/applicants/{0}/", True),
    "jobs:applied-applicant-view":
        ("/employer/dashboard/applied-applicant/{0}/view/{1}", True),
    "jobs:job-mark-filled": ("/employer/dashboard/mark-filled/{0}/", True),
    "jobs:applicant-send-response": ("/employer/dashboard/send-response/{0}", True),
    "jobs:employer-jobs-create": ("/employer/dashboard/jobs/create/", True),
    "jobs:employer-jobs-edit": ("/employer/dashboard/jobs/{0}/edit/", True),
    "jobs:company-create": ("/employer/dashboard/company/create/", True),
    "jobs:company-edit": ("/employer/dashboard/company/{0}/edit/", True),
    "jobs:employee-my-applications": ("/employee/my-applications", True),
    "jobs:employee-favorites": ("/employee/favorites", True),
    "accounts:employee-register": ("/employee/register/", True),
    "accounts:employer-register": ("/employer/register/", True),
    "accounts:employee-profile-update": ("/employee/profile/update/", True),
    "accounts:employer-profile-update": ("/employer/profile/update/", True),
    "accounts:login": ("/login/", True),
    "accounts:logout": ("/logout/", True),
    "resume_cv:templates": ("/templates", True),
    "resume_cv:create": ("/resume-cv/create", True),
    "resume_cv:builder": ("/templates/builder/{0}", True),
    "resume_cv:resumes": ("/resumes/", True),
    "set_language": ("/i18n/setlang/", False),
    "resume-cv.load.builder": ("/templates/load-builder/{0}", False),
    "resume-cv.update.builder": ("/templates/update-builder/{0}", False),
}


def reverse(name: str, *args, language: str | None = None) -> str:
    """Build the path a named route points at."""
    try:
        template, prefixed = ROUTES[name]
    except KeyError:
        raise LookupError("no route is named %r" % name) from None
    path = template.format(*args)
    if prefixed:
        return "/%s%s" % (language or settings.language_code, path)
    return path
