"""add user profile fields

Revision ID: 005_user_profile
Revises: 004_follows
Create Date: 2025-12-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_user_profile'
down_revision: Union[str, None] = '004_follows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加用户资料扩展字段
    op.add_column('users', sa.Column('gender', sa.String(10), server_default='male'))
    op.add_column('users', sa.Column('location', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('school', sa.String(100), nullable=True))


def downgrade() -> None:
    # 删除添加的字段
    op.drop_column('users', 'school')
    op.drop_column('users', 'location')
    op.drop_column('users', 'gender')
