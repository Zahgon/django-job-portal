"""Resume templates and the resumes built from them.

Revision ID: 0007_resume_cv
Revises: 0006_rename_category_index
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_resume_cv"
down_revision = "0006_rename_category_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resume_cv_resumecvcategory",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("thumbnail", sa.String(length=100), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "resume_cv_resumecvtemplate",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("thumbnail", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("style", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_premium", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["resume_cv_resumecvcategory.id"]),
    )
    op.create_index("resume_cv_resumecvtemplate_category_id_idx",
                    "resume_cv_resumecvtemplate", ["category_id"])
    op.create_table(
        "resume_cv_resumecv",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.CHAR(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("style", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["accounts_user.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["resume_cv_resumecvtemplate.id"]),
    )
    op.create_index("resume_cv_resumecv_user_id_idx", "resume_cv_resumecv",
                    ["user_id"])
    op.create_index("resume_cv_resumecv_template_id_idx", "resume_cv_resumecv",
                    ["template_id"])


def downgrade() -> None:
    op.drop_table("resume_cv_resumecv")
    op.drop_table("resume_cv_resumecvtemplate")
    op.drop_table("resume_cv_resumecvcategory")
