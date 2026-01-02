"""Add interaction flows and sessions tables

Revision ID: 011b
Revises: 011a
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

revision = '011b'
down_revision = '011a'
branch_labels = None
depends_on = None


def upgrade():
    # Create interaction_flows table
    op.create_table(
        'interaction_flows',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('flow_id', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('trigger_patterns', JSONB, server_default='[]'),
        sa.Column('scenario_id', sa.String(50), nullable=True),
        sa.Column('steps', JSONB, nullable=False),
        sa.Column('on_complete', sa.String(30), server_default='generate'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index('ix_interaction_flows_flow_id', 'interaction_flows', ['flow_id'], unique=True)
    op.create_index('ix_interaction_flows_scenario_id', 'interaction_flows', ['scenario_id'])

    # Create interaction_sessions table
    op.create_table(
        'interaction_sessions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_id', sa.String(50), unique=True, nullable=False),
        sa.Column('conversation_id', sa.String(50), nullable=False),
        sa.Column('flow_id', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('current_step', sa.Integer, server_default='0'),
        sa.Column('collected_answers', JSONB, server_default='{}'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index('ix_interaction_sessions_session_id', 'interaction_sessions', ['session_id'], unique=True)
    op.create_index('ix_interaction_sessions_conversation_id', 'interaction_sessions', ['conversation_id'])
    op.create_index('ix_interaction_sessions_status', 'interaction_sessions', ['status'])


def downgrade():
    op.drop_index('ix_interaction_sessions_status', table_name='interaction_sessions')
    op.drop_index('ix_interaction_sessions_conversation_id', table_name='interaction_sessions')
    op.drop_index('ix_interaction_sessions_session_id', table_name='interaction_sessions')
    op.drop_table('interaction_sessions')
    
    op.drop_index('ix_interaction_flows_scenario_id', table_name='interaction_flows')
    op.drop_index('ix_interaction_flows_flow_id', table_name='interaction_flows')
    op.drop_table('interaction_flows')

