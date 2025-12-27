"""add conversation summary table

Revision ID: 006
Revises: 005
Create Date: 2024-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 对话摘要表
    op.create_table(
        'conversation_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.String(100), nullable=False, index=True),
        sa.Column('summary_type', sa.String(50), nullable=False),  # instant/session/topic
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('key_points', JSONB, nullable=True),
        sa.Column('entities_mentioned', JSONB, nullable=True),
        sa.Column('topics', JSONB, nullable=True),
        sa.Column('turn_count', sa.Integer(), default=0),
        sa.Column('turn_start', sa.Integer(), default=0),
        sa.Column('turn_end', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # 创建索引
    op.create_index(
        'idx_summaries_conv_type',
        'conversation_summaries',
        ['conversation_id', 'summary_type'],
    )


def downgrade() -> None:
    op.drop_index('idx_summaries_conv_type')
    op.drop_table('conversation_summaries')

