"""Fix missing tables - ensure all required tables exist

Revision ID: 014
Revises: 013
Create Date: 2026-01-03

This migration ensures all tables that may have been skipped due to
migration renaming issues are properly created.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"
    ), {"name": table_name})
    return result.scalar()


def upgrade() -> None:
    # Create notifications table if not exists
    if not table_exists('notifications'):
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('notification_type', sa.String(50), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('message', sa.Text()),
            sa.Column('related_type', sa.String(50)),
            sa.Column('related_id', sa.Integer()),
            sa.Column('is_read', sa.Boolean(), default=False),
            sa.Column('read_at', sa.DateTime()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('idx_notifications_user_id', 'notifications', ['user_id'])
        op.create_index('idx_notifications_is_read', 'notifications', ['is_read'])
    
    # Create interaction_flows table if not exists
    if not table_exists('interaction_flows'):
        op.create_table(
            'interaction_flows',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('flow_code', sa.String(50), unique=True, nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('trigger_keywords', JSONB, server_default='[]'),
            sa.Column('trigger_intents', JSONB, server_default='[]'),
            sa.Column('steps', JSONB, server_default='[]'),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('priority', sa.Integer(), default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
    
    # Create interaction_sessions table if not exists
    if not table_exists('interaction_sessions'):
        op.create_table(
            'interaction_sessions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('session_id', sa.String(100), unique=True, nullable=False),
            sa.Column('flow_id', sa.Integer(), sa.ForeignKey('interaction_flows.id')),
            sa.Column('conversation_id', sa.Integer()),
            sa.Column('user_id', sa.Integer()),
            sa.Column('current_step', sa.Integer(), default=0),
            sa.Column('collected_answers', JSONB, server_default='{}'),
            sa.Column('status', sa.String(20), default='active'),
            sa.Column('context', JSONB, server_default='{}'),
            sa.Column('dynamic_mode', sa.Boolean(), default=False),
            sa.Column('intent_type', sa.String(50)),
            sa.Column('extracted_entities', JSONB, server_default='{}'),
            sa.Column('pending_question', JSONB),
            sa.Column('search_executed', sa.Boolean(), default=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
    else:
        # Add missing columns to interaction_sessions if they don't exist
        conn = op.get_bind()
        
        # Check and add dynamic_mode column
        result = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'interaction_sessions' AND column_name = 'dynamic_mode')"
        ))
        if not result.scalar():
            op.add_column('interaction_sessions', sa.Column('dynamic_mode', sa.Boolean(), default=False))
        
        # Check and add intent_type column
        result = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'interaction_sessions' AND column_name = 'intent_type')"
        ))
        if not result.scalar():
            op.add_column('interaction_sessions', sa.Column('intent_type', sa.String(50)))
        
        # Check and add extracted_entities column
        result = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'interaction_sessions' AND column_name = 'extracted_entities')"
        ))
        if not result.scalar():
            op.add_column('interaction_sessions', sa.Column('extracted_entities', JSONB, server_default='{}'))
        
        # Check and add pending_question column
        result = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'interaction_sessions' AND column_name = 'pending_question')"
        ))
        if not result.scalar():
            op.add_column('interaction_sessions', sa.Column('pending_question', JSONB))
        
        # Check and add search_executed column
        result = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'interaction_sessions' AND column_name = 'search_executed')"
        ))
        if not result.scalar():
            op.add_column('interaction_sessions', sa.Column('search_executed', sa.Boolean(), default=False))
    
    # Ensure knowledge_units table has all required columns for indexing pipeline
    if table_exists('knowledge_units'):
        ku_columns = [
            ('source_file', 'VARCHAR(500)'),
            ('scenario_tags', 'JSONB'),
            ('key_points_json', 'JSONB'),
            ('params_json', 'JSONB'),
            ('tags_json', 'JSONB'),
        ]
        conn = op.get_bind()
        for col_name, col_type in ku_columns:
            result = conn.execute(sa.text(
                "SELECT EXISTS (SELECT FROM information_schema.columns "
                "WHERE table_name = 'knowledge_units' AND column_name = :col)"
            ), {"col": col_name})
            if not result.scalar():
                op.execute(f'ALTER TABLE knowledge_units ADD COLUMN {col_name} {col_type}')
                print(f"Added column {col_name} to knowledge_units")


def downgrade() -> None:
    # We don't drop tables on downgrade to preserve data
    # Only remove columns that were added in this migration if needed
    pass

