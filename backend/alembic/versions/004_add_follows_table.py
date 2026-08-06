"""add follows table

Revision ID: 004_follows
Revises: 003_triggers
Create Date: 2025-01-XX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_follows'
down_revision: Union[str, None] = '003_triggers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建关注关系表
    op.create_table(
        'follows',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('follower_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('following_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], name='follows_follower_id_fkey'),
        sa.ForeignKeyConstraint(['following_id'], ['users.id'], name='follows_following_id_fkey'),
    )
    
    # 创建索引
    op.create_index('idx_follows_follower_id', 'follows', ['follower_id'])
    op.create_index('idx_follows_following_id', 'follows', ['following_id'])
    op.create_index('idx_follows_follower_following', 'follows', ['follower_id', 'following_id'], unique=True)
    
    # 添加触发器自动更新updated_at（虽然follows表没有updated_at字段，但保持一致性）
    # 注意：follows表只有created_at，不需要updated_at触发器


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_follows_follower_following', table_name='follows')
    op.drop_index('idx_follows_following_id', table_name='follows')
    op.drop_index('idx_follows_follower_id', table_name='follows')
    
    # 删除表
    op.drop_table('follows')

