"""initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-XX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建uuid-ossp扩展（PostgreSQL）
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # 创建所有表（表结构已在models.py中定义，这里只创建迁移占位）
    # 实际表结构应该通过Base.metadata.create_all()创建
    # 或者通过alembic revision --autogenerate生成
    
    # 注意：此迁移文件是占位符
    # 实际使用时应该运行: alembic revision --autogenerate -m "initial migration"
    # 来生成完整的表结构迁移
    
    pass


def downgrade() -> None:
    # 删除所有表
    pass

