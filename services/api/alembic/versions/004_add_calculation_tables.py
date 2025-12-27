"""add calculation rules and parameter definitions tables

Revision ID: 004
Revises: 0001
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '004'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # 计算规则配置表
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
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 参数标准定义表
    op.create_table(
        'parameter_definitions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('scenario_id', sa.String(64), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('canonical_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('param_type', sa.String(50), nullable=True),  # performance/spec/price/scope
        sa.Column('value_type', sa.String(20), nullable=True),  # number/range/enum
        sa.Column('enum_values', JSONB, default=[]),
        sa.Column('default_range', JSONB, default={}),
        sa.Column('better_direction', sa.String(20), default='higher'),  # higher/lower/neutral
        sa.Column('aliases', JSONB, default=[]),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # 索引
    op.create_index('ix_calculation_rules_scenario', 'calculation_rules', ['scenario_id'])
    op.create_index('ix_calculation_rules_type', 'calculation_rules', ['calculation_type'])
    op.create_index('ix_parameter_definitions_scenario', 'parameter_definitions', ['scenario_id'])
    op.create_index('ix_parameter_definitions_name', 'parameter_definitions', ['canonical_name'])


def downgrade():
    op.drop_index('ix_parameter_definitions_name')
    op.drop_index('ix_parameter_definitions_scenario')
    op.drop_index('ix_calculation_rules_type')
    op.drop_index('ix_calculation_rules_scenario')
    op.drop_table('parameter_definitions')
    op.drop_table('calculation_rules')

