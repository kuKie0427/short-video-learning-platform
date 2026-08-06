"""add database triggers

Revision ID: 003_triggers
Revises: 002_gin_indexes
Create Date: 2025-01-XX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_triggers'
down_revision: Union[str, None] = '002_gin_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建更新updated_at字段的函数
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 为所有表添加BEFORE UPDATE触发器更新updated_at
    tables_with_updated_at = [
        'users', 'videos', 'learn_records', 'comments', 'likes', 
        'favorites', 'upload_tasks', 'notifications', 'long_videos',
        'split_tasks', 'split_segments', 'courses', 'course_videos'
    ]
    
    for table_name in tables_with_updated_at:
        trigger_name = f'update_{table_name}_updated_at'
        op.execute(f"""
            DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};
            CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # 创建更新课程统计信息的函数
    op.execute("""
        CREATE OR REPLACE FUNCTION update_course_stats()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE courses 
                SET total_videos = total_videos + 1,
                    total_duration = total_duration + (
                        SELECT duration FROM videos WHERE id = NEW.video_id
                    )
                WHERE id = NEW.course_id;
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE courses 
                SET total_videos = total_videos - 1,
                    total_duration = total_duration - (
                        SELECT duration FROM videos WHERE id = OLD.video_id
                    )
                WHERE id = OLD.course_id;
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 为course_videos表添加触发器自动更新课程统计信息
    op.execute("""
        DROP TRIGGER IF EXISTS update_course_stats_trigger ON course_videos;
        CREATE TRIGGER update_course_stats_trigger
            AFTER INSERT OR DELETE ON course_videos
            FOR EACH ROW
            EXECUTE FUNCTION update_course_stats();
    """)


def downgrade() -> None:
    # 删除触发器
    tables_with_updated_at = [
        'users', 'videos', 'learn_records', 'comments', 'likes', 
        'favorites', 'upload_tasks', 'notifications', 'long_videos',
        'split_tasks', 'split_segments', 'courses', 'course_videos'
    ]
    
    for table_name in tables_with_updated_at:
        trigger_name = f'update_{table_name}_updated_at'
        op.execute(f'DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};')
    
    op.execute('DROP TRIGGER IF EXISTS update_course_stats_trigger ON course_videos;')
    
    # 删除函数
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column();')
    op.execute('DROP FUNCTION IF EXISTS update_course_stats();')

