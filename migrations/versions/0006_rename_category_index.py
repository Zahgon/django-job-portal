"""The category index is renamed; the index itself is unchanged.

Revision ID: 0006_rename_category_index
Revises: 0005_job_category
"""
from alembic import op

revision = "0006_rename_category_index"
down_revision = "0005_job_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("jobsapp_job_category_idx", table_name="jobsapp_job")
    op.create_index("jobsapp_job_categor_e9323e_idx", "jobsapp_job",
                    ["category_id"])


def downgrade() -> None:
    op.drop_index("jobsapp_job_categor_e9323e_idx", table_name="jobsapp_job")
    op.create_index("jobsapp_job_category_idx", "jobsapp_job", ["category_id"])
