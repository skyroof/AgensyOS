"""update_telegram_id_to_bigint

Revision ID: a1b2c3d4e5f6
Revises: 891694713801
Create Date: 2026-01-05 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '891694713801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change telegram_id type from Integer to BigInteger
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('telegram_id',
                   existing_type=sa.Integer(),
                   type_=sa.BigInteger(),
                   existing_nullable=False)


def downgrade() -> None:
    # Change telegram_id type back to Integer
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('telegram_id',
                   existing_type=sa.BigInteger(),
                   type_=sa.Integer(),
                   existing_nullable=False)
