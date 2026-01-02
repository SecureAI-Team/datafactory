"""Add pipeline KU columns

Revision ID: 013_add_pipeline_ku_columns
Revises: 012_add_dynamic_interaction_columns
Create Date: 2026-01-02

Add columns needed for pipeline indexing:
- source_file: Track original source file
- scenario_tags: Scenario tags from pipeline
- key_points_json: Key points extracted
- params_json: Structured parameters
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for pipeline integration
    op.add_column('knowledge_units', 
        sa.Column('source_file', sa.String(500), nullable=True))
    op.add_column('knowledge_units', 
        sa.Column('scenario_tags', JSONB, server_default='[]'))
    op.add_column('knowledge_units', 
        sa.Column('key_points_json', JSONB, server_default='[]'))
    op.add_column('knowledge_units', 
        sa.Column('params_json', JSONB, server_default='[]'))
    
    # Create index on source_file for quick lookups
    op.create_index('idx_ku_source_file', 'knowledge_units', ['source_file'])


def downgrade():
    op.drop_index('idx_ku_source_file', 'knowledge_units')
    op.drop_column('knowledge_units', 'params_json')
    op.drop_column('knowledge_units', 'key_points_json')
    op.drop_column('knowledge_units', 'scenario_tags')
    op.drop_column('knowledge_units', 'source_file')

