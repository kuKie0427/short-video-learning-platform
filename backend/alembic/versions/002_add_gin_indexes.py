"""add gin indexes

Revision ID: 002_gin_indexes
Revises: 001_initial
Create Date: 2025-01-XX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_gin_indexes'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为videos表的tags字段添加GIN索引
    # 注意：GIN索引需要PostgreSQL扩展支持
    op.execute('CREATE INDEX IF NOT EXISTS idx_videos_tags ON videos USING GIN(tags)')
    
    # 为courses表的tags字段添加GIN索引
    op.execute('CREATE INDEX IF NOT EXISTS idx_courses_tags ON courses USING GIN(tags)')


def downgrade() -> None:
    # 删除GIN索引
    op.execute('DROP INDEX IF EXISTS idx_videos_tags')
    op.execute('DROP INDEX IF EXISTS idx_courses_tags')

