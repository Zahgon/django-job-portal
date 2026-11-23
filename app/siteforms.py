"""The site's own forms: registration, signing in, profiles, jobs, companies."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.forms import (
    CharField, DateTimeField, DecimalField, EMAIL_TAKEN, EmailField, Field,
    Form, IntegerField, ModelChoiceField, ModelMultipleChoiceField,
    PASSWORD_MISMATCH, PASSWORD_TOO_SHORT, URLField, ValidationError,
)
from app.models import (
    Category, Company, CompanySize, ExperienceLevel, GENDER_CHOICES, Job,
    JobStatus, JobType, SalaryPeriod, Tag, User, WorkplaceType,
)
from app.security import check_password, make_password

SALARY_CURRENCIES = (("BDT", "BDT"), ("USD", "USD"), ("EUR", "EUR"),
                     ("GBP", "GBP"), ("INR", "INR"))


class RegistrationForm(Form):
    """Shared behaviour of the two sign-up forms."""

    role = "employee"
    with_gender = True

    def declare(self):
        fields = [
            ("first_name", CharField(max_length=150)),
            ("last_name", CharField(max_length=150)),
            ("email", EmailField(max_length=254)),
            ("password1", CharField(label="Password")),
            ("password2", CharField(label="Confirm Password")),
        ]
        if self.with_gender:
            fields.append(
                ("gender", Field(choices=GENDER_CHOICES, label="Gender",
                                 required=False))
            )
        return fields

    def clean_email(self):
        email = self.cleaned_data["email"]
        taken = self.session.scalar(select(User).where(User.email == email))
        if taken is not None:
            raise ValidationError(EMAIL_TAKEN)
        return email

    def clean_gender(self):
        gender = self.cleaned_data.get("gender")
        if not gender:
            raise ValidationError("Gender is required")
        return gender

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(PASSWORD_MISMATCH)
        if password2 is not None and len(password2) < 5:
            raise ValidationError(PASSWORD_TOO_SHORT)
        return password2

    def save(self) -> User:
        user = User(
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data["email"],
            gender=self.cleaned_data.get("gender", ""),
            role=self.role,
            password=make_password(self.cleaned_data["password1"]),
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        self.session.add(user)
        self.session.commit()
        return user


class EmployeeRegistrationForm(RegistrationForm):
    """A candidate signing up; the gender field is required here."""

    role = "employee"
    with_gender = True


class EmployerRegistrationForm(RegistrationForm):
    """An employer signing up; the name fields carry company wording."""

    role = "employer"
    with_gender = False

    def declare(self):
        fields = dict(super().declare())
        fields["first_name"].label = "Company Name"
        fields["last_name"].label = "Company Address"
        return list(fields.items())


class LoginForm(Form):
    """Signing in with an e-mail address and a password."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def declare(self):
        return [("email", EmailField()), ("password", CharField(label="Password"))]

    def clean(self):
        email = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")
        if not email or not password:
            return
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None or not user.is_active or \
                not check_password(password, user.password):
            raise ValidationError("User Does Not Exist.")
        self.user = user

    def get_user(self) -> User | None:
        return self.user


class EmployeeProfileForm(Form):
    """What a candidate may change about their own account."""

    def declare(self):
        return [
            ("first_name", CharField(max_length=150, required=False)),
            ("last_name", CharField(max_length=150, required=False)),
            ("gender", Field(choices=GENDER_CHOICES, required=False)),
        ]

    def save(self) -> User:
        for name in ("first_name", "last_name", "gender"):
            setattr(self.instance, name, self.cleaned_data.get(name) or "")
        self.session.commit()
        return self.instance


class EmployerProfileForm(Form):
    """What an employer may change about their own account."""

    def declare(self):
        return [
            ("first_name", CharField(max_length=150, required=False,
                                     label="Company name")),
            ("last_name", CharField(max_length=150, required=False,
                                    label="Company address")),
        ]

    def save(self) -> User:
        for name in ("first_name", "last_name"):
            setattr(self.instance, name, self.cleaned_data.get(name) or "")
        self.session.commit()
        return self.instance


class CompanyForm(Form):
    """Creating or editing an employer profile."""

    def declare(self):
        return [
            ("name", CharField(max_length=100, label="Company Name")),
            ("description", CharField(max_length=1000, required=False,
                                      label="Company Description")),
            ("website", URLField(max_length=200, required=False,
                                 label="Company Website")),
            ("logo", CharField(required=False, label="Company Logo")),
            ("industry", CharField(max_length=100, required=False,
                                   label="Industry")),
            ("size", Field(choices=CompanySize.CHOICES, required=False,
                           label="Company Size")),
            ("culture_benefits", CharField(required=False,
                                           label="Culture & Benefits")),
        ]

    EMPTY_IS_NULL = ("description", "website", "industry", "culture_benefits")

    def save(self, user) -> Company:
        company = self.instance or Company(user_id=user.id)
        for name in ("description", "website", "industry", "culture_benefits",
                     "size", "logo"):
            value = self.cleaned_data.get(name) or ""
            setattr(company, name, value or
                    (None if name in self.EMPTY_IS_NULL else ""))
        company.name = self.cleaned_data["name"]
        company.cover_image = company.cover_image or ""
        company.user_id = user.id
        company.ensure_slug()
        self.session.add(company)
        self.session.commit()
        return company


class JobForm(Form):
    """Posting or editing a job."""

    def declare(self):
        session = self.session
        return [
            ("company", ModelChoiceField(
                lambda key: session.get(Company, key), label="Company profile")),
            ("category", ModelChoiceField(
                lambda key: session.get(Category, key), label="Category")),
            ("title", CharField(max_length=300)),
            ("description", CharField()),
            ("responsibilities", CharField(required=False)),
            ("requirements", CharField(required=False)),
            ("location", CharField(max_length=200)),
            ("type", Field(choices=JobType.CHOICES)),
            ("workplace_type", Field(choices=WorkplaceType.CHOICES,
                                     label="Workplace type")),
            ("experience_level", Field(choices=ExperienceLevel.CHOICES,
                                       label="Experience level")),
            ("application_deadline", DateTimeField(label="Application deadline")),
            ("filled", Field(required=False)),
            ("status", Field(choices=JobStatus.CHOICES)),
            ("salary", IntegerField(required=False)),
            ("salary_min", DecimalField(required=False)),
            ("salary_max", DecimalField(required=False)),
            ("salary_currency", Field(choices=SALARY_CURRENCIES,
                                      label="Salary currency")),
            ("salary_period", Field(choices=SalaryPeriod.CHOICES,
                                    label="Salary period")),
            ("tags", ModelMultipleChoiceField(
                lambda key: session.get(Tag, key), label="Tags")),
            ("vacancy", IntegerField()),
            ("is_featured", Field(required=False)),
        ]

    def clean_application_deadline(self):
        value = self.cleaned_data["application_deadline"]
        if value.date() < date.today():
            raise ValidationError("Application deadline can't be before today")
        return value

    def clean_tags(self):
        tags = self.cleaned_data["tags"]
        if len(tags) > 6:
            raise ValidationError("You can't add more than 6 tags")
        return tags

    def save(self, user) -> Job:
        job = self.instance or Job()
        data = self.cleaned_data
        job.user_id = user.id
        job.company_id = data["company"].id
        job.category_id = data["category"].id
        job.title = data["title"]
        job.description = data["description"]
        job.responsibilities = data.get("responsibilities") or ""
        job.requirements = data.get("requirements") or ""
        job.location = data["location"]
        job.type = data["type"]
        job.workplace_type = data["workplace_type"]
        job.experience_level = data["experience_level"]
        job.application_deadline = data["application_deadline"]
        job.filled = bool(data.get("filled"))
        job.status = data["status"]
        job.salary = data.get("salary") or 0
        job.salary_min = data.get("salary_min")
        job.salary_max = data.get("salary_max")
        job.salary_currency = data["salary_currency"]
        job.salary_period = data["salary_period"]
        job.vacancy = data["vacancy"]
        job.is_featured = bool(data.get("is_featured"))
        job.ensure_slug()
        self.session.add(job)
        self.session.flush()
        for tag in data["tags"]:
            if tag not in job.tags:
                job.tags.append(tag)
        self.session.commit()
        return job
