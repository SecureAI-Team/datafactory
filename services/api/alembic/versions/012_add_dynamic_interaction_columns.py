"""Add dynamic interaction columns to interaction_sessions

Revision ID: 012
Revises: 011b
Create Date: 2025-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011b'
branch_labels = None
depends_on = None


def upgrade():
    """Add new columns to interaction_sessions for dynamic mode support"""
    # Add is_dynamic column
    op.add_column('interaction_sessions', 
        sa.Column('is_dynamic', sa.Boolean(), nullable=True, default=False)
    )
    
    # Add intent_context column for storing intent recognition results
    op.add_column('interaction_sessions',
        sa.Column('intent_context', JSONB, nullable=True, default={})
    )
    
    # Add original_query column for storing the user's original question
    op.add_column('interaction_sessions',
        sa.Column('original_query', sa.Text(), nullable=True)
    )
    
    # Add questions_asked column for storing dynamically generated questions
    op.add_column('interaction_sessions',
        sa.Column('questions_asked', JSONB, nullable=True, default=[])
    )
    
    # Add optimized_query column for LLM-optimized search query
    op.add_column('interaction_sessions',
        sa.Column('optimized_query', sa.Text(), nullable=True)
    )
    
    # Make flow_id nullable for dynamic mode
    op.alter_column('interaction_sessions', 'flow_id',
        existing_type=sa.String(50),
        nullable=True
    )
    
    # Set default value for is_dynamic on existing rows
    op.execute("UPDATE interaction_sessions SET is_dynamic = FALSE WHERE is_dynamic IS NULL")


def downgrade():
    """Remove dynamic interaction columns"""
    op.drop_column('interaction_sessions', 'optimized_query')
    op.drop_column('interaction_sessions', 'questions_asked')
    op.drop_column('interaction_sessions', 'original_query')
    op.drop_column('interaction_sessions', 'intent_context')
    op.drop_column('interaction_sessions', 'is_dynamic')
    
    # Restore flow_id to not nullable
    op.alter_column('interaction_sessions', 'flow_id',
        existing_type=sa.String(50),
        nullable=False
    )

