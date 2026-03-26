"""Add invite_token and invite_accepted_at to users

Revision ID: 001_invite_token
Revises: None
Create Date: 2026-03-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_invite_token"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("invite_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("invite_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_users_invite_token", "users", ["invite_token"])


def downgrade() -> None:
    op.drop_constraint("uq_users_invite_token", "users", type_="unique")
    op.drop_column("users", "invite_accepted_at")
    op.drop_column("users", "invite_token")
