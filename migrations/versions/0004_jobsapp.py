"""Companies, postings, applications and saved postings.

Revision ID: 0004_jobsapp
Revises: 0003_categories
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_jobsapp"
down_revision = "0003_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobsapp_company",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("tagline", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("logo", sa.String(length=100), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("headquarters", sa.String(length=150), nullable=True),
        sa.Column("size", sa.String(length=20), nullable=False),
        sa.Column("culture_benefits", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("linkedin_url", sa.String(length=200), nullable=True),
        sa.Column("facebook_url", sa.String(length=200), nullable=True),
        sa.Column("cover_image", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["accounts_user.id"]),
        sa.UniqueConstraint("slug", name="jobsapp_company_slug_key"),
        sa.UniqueConstraint("user_id", "name", name="uniq_company_name_per_owner"),
    )
    op.create_index("jobsapp_company_user_id_idx", "jobsapp_company", ["user_id"])

    op.create_table(
        "jobsapp_job",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("slug", sa.String(length=340), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsibilities", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("workplace_type", sa.String(length=20), nullable=False),
        sa.Column("experience_level", sa.String(length=20), nullable=False),
        sa.Column("application_deadline", sa.DateTime(), nullable=False),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("filled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("salary", sa.Integer(), nullable=False),
        sa.Column("salary_min", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=5), nullable=False),
        sa.Column("salary_period", sa.String(length=10), nullable=False),
        sa.Column("vacancy", sa.Integer(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["jobsapp_company.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["accounts_user.id"]),
    )
    op.create_index("jobsapp_job_slug_idx", "jobsapp_job", ["slug"])
    op.create_index("jobsapp_job_company_id_idx", "jobsapp_job", ["company_id"])
    op.create_index("jobsapp_job_user_id_idx", "jobsapp_job", ["user_id"])
    op.create_index("jobsapp_job_status_88565f_idx", "jobsapp_job",
                    ["status", "filled"])
    op.create_index("jobsapp_job_type_b00a27_idx", "jobsapp_job",
                    ["type", "workplace_type"])
    op.create_index("jobsapp_job_created_bcca72_idx", "jobsapp_job", ["created_at"])
    op.create_index("jobsapp_job_applica_564e1a_idx", "jobsapp_job",
                    ["application_deadline"])

    op.create_table(
        "jobsapp_job_tags",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobsapp_job.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags_tag.id"]),
        sa.UniqueConstraint("job_id", "tag_id",
                            name="jobsapp_job_tags_job_id_tag_id_uniq"),
    )
    op.create_index("jobsapp_job_tags_job_id_idx", "jobsapp_job_tags", ["job_id"])
    op.create_index("jobsapp_job_tags_tag_id_idx", "jobsapp_job_tags", ["tag_id"])

    op.create_table(
        "jobsapp_favorite",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("soft_deleted", sa.Boolean(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["accounts_user.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobsapp_job.id"]),
    )
    op.create_index("jobsapp_favorite_user_id_idx", "jobsapp_favorite", ["user_id"])
    op.create_index("jobsapp_favorite_job_id_idx", "jobsapp_favorite", ["job_id"])

    op.create_table(
        "jobsapp_applicant",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["accounts_user.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobsapp_job.id"]),
        sa.UniqueConstraint("user_id", "job_id",
                            name="jobsapp_applicant_user_id_job_id_uniq"),
    )
    op.create_index("jobsapp_applicant_user_id_idx", "jobsapp_applicant",
                    ["user_id"])
    op.create_index("jobsapp_applicant_job_id_idx", "jobsapp_applicant", ["job_id"])


def downgrade() -> None:
    op.drop_table("jobsapp_applicant")
    op.drop_table("jobsapp_favorite")
    op.drop_table("jobsapp_job_tags")
    op.drop_table("jobsapp_job")
    op.drop_table("jobsapp_company")
