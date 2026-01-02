"""add_pdp_gamification

Revision ID: 891694713801
Revises: 6c2a4d9c3f1b
Create Date: 2026-01-02 19:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "891694713801"
down_revision: Union[str, None] = "6c2a4d9c3f1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add xp to pdp_tasks
    op.add_column('pdp_tasks', sa.Column('xp', sa.Integer(), server_default='10', nullable=False))
    
    # Add reflections to pdp_plans
    op.add_column('pdp_plans', sa.Column('reflections', sa.JSON(), nullable=True))
    
    # Create task_reminders table
    op.create_table(
        'task_reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('sent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['pdp_tasks.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_reminders_scheduled_at'), 'task_reminders', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_task_reminders_task_id'), 'task_reminders', ['task_id'], unique=False)
    op.create_index(op.f('ix_task_reminders_user_id'), 'task_reminders', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_task_reminders_user_id'), table_name='task_reminders')
    op.drop_index(op.f('ix_task_reminders_task_id'), table_name='task_reminders')
    op.drop_index(op.f('ix_task_reminders_scheduled_at'), table_name='task_reminders')
    op.drop_table('task_reminders')
    op.drop_column('pdp_plans', 'reflections')
    op.drop_column('pdp_tasks', 'xp')
