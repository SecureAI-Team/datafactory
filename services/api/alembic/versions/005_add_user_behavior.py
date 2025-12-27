"""add user behavior tables

Revision ID: 005
Revises: 004
Create Date: 2024-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 用户行为记录表
    op.create_table(
        'user_behaviors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False, index=True),
        sa.Column('session_id', sa.String(100), nullable=True, index=True),
        sa.Column('behavior_type', sa.String(50), nullable=False),  # query/view/click/feedback
        sa.Column('target_type', sa.String(50), nullable=True),     # ku/document/scenario
        sa.Column('target_id', sa.String(200), nullable=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('intent_type', sa.String(50), nullable=True),
        sa.Column('scenario_id', sa.String(100), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # KU 访问统计表
    op.create_table(
        'ku_access_stats',
        sa.Column('ku_id', sa.String(200), primary_key=True),
        sa.Column('view_count', sa.Integer(), default=0),
        sa.Column('click_count', sa.Integer(), default=0),
        sa.Column('feedback_positive', sa.Integer(), default=0),
        sa.Column('feedback_negative', sa.Integer(), default=0),
        sa.Column('avg_rating', sa.Float(), nullable=True),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 用户偏好表
    op.create_table(
        'user_preferences',
        sa.Column('user_id', sa.String(100), primary_key=True),
        sa.Column('preferred_scenarios', JSONB, nullable=True),
        sa.Column('preferred_intents', JSONB, nullable=True),
        sa.Column('recent_queries', JSONB, nullable=True),
        sa.Column('topic_interests', JSONB, nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 创建索引
    op.create_index('idx_behaviors_user_time', 'user_behaviors', ['user_id', 'created_at'])
    op.create_index('idx_behaviors_type_target', 'user_behaviors', ['behavior_type', 'target_type'])


def downgrade() -> None:
    op.drop_index('idx_behaviors_type_target')
    op.drop_index('idx_behaviors_user_time')
    op.drop_table('user_preferences')
    op.drop_table('ku_access_stats')
    op.drop_table('user_behaviors')

