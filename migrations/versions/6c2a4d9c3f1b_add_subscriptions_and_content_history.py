"""add_subscriptions_and_content_history

Revision ID: 6c2a4d9c3f1b
Revises: fa08158b3320
Create Date: 2025-12-31 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c2a4d9c3f1b"
down_revision: Union[str, None] = "fa08158b3320"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "user_subscriptions" not in existing_tables:
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("start_date", sa.DateTime(), nullable=True),
            sa.Column("end_date", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_user_subscriptions_user_id"),
            "user_subscriptions",
            ["user_id"],
            unique=True,
        )

    if "user_content_history" not in existing_tables:
        op.create_table(
            "user_content_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("content_type", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=True),
            sa.Column("metric", sa.String(length=50), nullable=False),
            sa.Column("reason", sa.String(length=50), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_user_content_history_user_id"),
            "user_content_history",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "ix_user_content_history_user_id_sent_at",
            "user_content_history",
            ["user_id", "sent_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "user_content_history" in existing_tables:
        op.drop_index(
            "ix_user_content_history_user_id_sent_at", table_name="user_content_history"
        )
        op.drop_index(
            op.f("ix_user_content_history_user_id"), table_name="user_content_history"
        )
        op.drop_table("user_content_history")

    if "user_subscriptions" in existing_tables:
        op.drop_index(
            op.f("ix_user_subscriptions_user_id"), table_name="user_subscriptions"
        )
        op.drop_table("user_subscriptions")
