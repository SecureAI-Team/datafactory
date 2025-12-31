"""fix parameter_definitions and calculation_rules tables to match model

Revision ID: 010
Revises: 009
Create Date: 2025-01-01

This migration drops and recreates the parameter_definitions and calculation_rules
tables to match the updated SQLAlchemy models.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Drop old tables (they have incompatible schema)
    op.drop_index('ix_parameter_definitions_name', table_name='parameter_definitions', if_exists=True)
    op.drop_index('ix_parameter_definitions_scenario', table_name='parameter_definitions', if_exists=True)
    op.drop_index('ix_calculation_rules_type', table_name='calculation_rules', if_exists=True)
    op.drop_index('ix_calculation_rules_scenario', table_name='calculation_rules', if_exists=True)
    
    op.drop_table('parameter_definitions', if_exists=True)
    op.drop_table('calculation_rules', if_exists=True)
    
    # Recreate parameter_definitions with correct schema
    op.create_table(
        'parameter_definitions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('data_type', sa.String(30), nullable=False),  # string/number/boolean/array
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('synonyms', JSONB, default=[]),
        sa.Column('validation_rules', JSONB, default={}),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('updated_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Recreate calculation_rules with correct schema
    op.create_table(
        'calculation_rules',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('formula', sa.Text, nullable=False),
        sa.Column('input_schema', JSONB, default={}),
        sa.Column('output_schema', JSONB, default={}),
        sa.Column('input_params', JSONB, default=[]),
        sa.Column('output_type', sa.String(30), default='number'),
        sa.Column('examples', JSONB, default=[]),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('updated_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_parameter_definitions_code', 'parameter_definitions', ['code'])
    op.create_index('ix_parameter_definitions_category', 'parameter_definitions', ['category'])
    op.create_index('ix_calculation_rules_code', 'calculation_rules', ['code'])


def downgrade():
    # Drop new tables
    op.drop_index('ix_calculation_rules_code', table_name='calculation_rules')
    op.drop_index('ix_parameter_definitions_category', table_name='parameter_definitions')
    op.drop_index('ix_parameter_definitions_code', table_name='parameter_definitions')
    
    op.drop_table('calculation_rules')
    op.drop_table('parameter_definitions')
    
    # Recreate old tables (from migration 004)
    op.create_table(
        'calculation_rules',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('scenario_id', sa.String(64), nullable=True),
        sa.Column('calculation_type', sa.String(50), nullable=False),
        sa.Column('trigger_patterns', JSONB, default=[]),
        sa.Column('required_inputs', JSONB, default=[]),
        sa.Column('optional_inputs', JSONB, default=[]),
        sa.Column('formula', sa.Text, nullable=True),
        sa.Column('output_template', sa.Text, nullable=True),
        sa.Column('default_values', JSONB, default={}),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    op.create_table(
        'parameter_definitions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('scenario_id', sa.String(64), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('canonical_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('param_type', sa.String(50), nullable=True),
        sa.Column('value_type', sa.String(20), nullable=True),
        sa.Column('enum_values', JSONB, default=[]),
        sa.Column('default_range', JSONB, default={}),
        sa.Column('better_direction', sa.String(20), default='higher'),
        sa.Column('aliases', JSONB, default=[]),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    op.create_index('ix_calculation_rules_scenario', 'calculation_rules', ['scenario_id'])
    op.create_index('ix_calculation_rules_type', 'calculation_rules', ['calculation_type'])
    op.create_index('ix_parameter_definitions_scenario', 'parameter_definitions', ['scenario_id'])
    op.create_index('ix_parameter_definitions_name', 'parameter_definitions', ['canonical_name'])

