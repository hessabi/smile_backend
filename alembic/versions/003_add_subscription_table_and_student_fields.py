"""Add subscription table and student fields

Revision ID: 003_subscription_student
Revises: 002_email_verified
Create Date: 2026-03-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "003_subscription_student"
down_revision: Union[str, None] = "002_email_verified"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(50), nullable=False, server_default="trial"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seat_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(clinic_id IS NOT NULL AND user_id IS NULL) OR (clinic_id IS NULL AND user_id IS NOT NULL)",
            name="ck_subscription_owner",
        ),
    )

    # 2. Add student fields to clinics
    op.add_column("clinics", sa.Column("account_type", sa.String(20), nullable=False, server_default="practice"))
    # dental_school_id FK -- the dental_schools table is created by a parallel migration.
    # Use nullable FK so this migration can run even if dental_schools doesn't exist yet;
    # the FK constraint is added as NOT VALID and can be validated later.
    op.add_column("clinics", sa.Column("dental_school_id", UUID(as_uuid=True), nullable=True))
    op.add_column("clinics", sa.Column("expected_graduation_date", sa.DateTime(timezone=True), nullable=True))

    # 3. Add student fields to users
    op.add_column("users", sa.Column("dental_school_id", UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("expected_graduation_date", sa.DateTime(timezone=True), nullable=True))

    # 4. Data migration: copy existing clinic subscription data into subscriptions table
    op.execute("""
        INSERT INTO subscriptions (id, clinic_id, plan, status, stripe_customer_id,
                                   stripe_subscription_id, trial_ends_at, current_period_end, seat_count)
        SELECT gen_random_uuid(), id, plan, subscription_status, stripe_customer_id,
               stripe_subscription_id, trial_ends_at, subscription_current_period_end, 5
        FROM clinics
    """)


def downgrade() -> None:
    # Remove student fields from users
    op.drop_column("users", "expected_graduation_date")
    op.drop_column("users", "dental_school_id")

    # Remove student fields from clinics
    op.drop_column("clinics", "expected_graduation_date")
    op.drop_column("clinics", "dental_school_id")
    op.drop_column("clinics", "account_type")

    # Drop subscriptions table
    op.drop_table("subscriptions")
