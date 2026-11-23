"""A posting belongs to a category.

Revision ID: 0005_job_category
Revises: 0004_jobsapp
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_job_category"
down_revision = "0004_jobsapp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobsapp_job") as batch:
        batch.add_column(sa.Column("category_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("jobsapp_job_category_id_fk", "categories_category",
                                 ["category_id"], ["id"])
    op.create_index("jobsapp_job_category_id_idx", "jobsapp_job", ["category_id"])
    op.create_index("jobsapp_job_category_idx", "jobsapp_job", ["category_id"])


def downgrade() -> None:
    op.drop_index("jobsapp_job_category_idx", table_name="jobsapp_job")
    op.drop_index("jobsapp_job_category_id_idx", table_name="jobsapp_job")
    with op.batch_alter_table("jobsapp_job") as batch:
        batch.drop_column("category_id")
