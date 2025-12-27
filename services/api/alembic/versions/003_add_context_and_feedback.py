"""add conversation context and feedback tables

Revision ID: 003
Revises: 002
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 对话上下文表
    op.create_table(
        'conversation_contexts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), unique=True, nullable=False, index=True),
        sa.Column('state', sa.String(32), nullable=False, default='active'),
        
        # JSON 字段存储复杂数据
        sa.Column('turns', sa.JSON, default=[]),
        sa.Column('entities', sa.JSON, default={}),
        sa.Column('preferences', sa.JSON, default={}),
        
        # 场景信息
        sa.Column('current_scenario', sa.String(64)),
        sa.Column('scenario_history', sa.JSON, default=[]),
        
        # 推荐跟踪
        sa.Column('recommended_solutions', sa.JSON, default=[]),
        sa.Column('solution_feedback', sa.JSON, default={}),
        
        # 澄清状态
        sa.Column('pending_clarification', sa.JSON),
        
        # 时间戳
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 反馈记录表
    op.create_table(
        'feedback_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), nullable=False, index=True),
        sa.Column('message_id', sa.String(36)),
        
        # 反馈信息
        sa.Column('feedback_type', sa.String(32), nullable=False),
        sa.Column('dimension', sa.String(32)),
        sa.Column('rating', sa.Integer),
        sa.Column('text', sa.Text),
        
        # 上下文信息
        sa.Column('query', sa.Text),
        sa.Column('response_preview', sa.Text),
        sa.Column('intent_type', sa.String(64)),
        sa.Column('scenario_id', sa.String(64)),
        
        # 处理状态
        sa.Column('processed', sa.Boolean, default=False),
        
        # 时间戳
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # 计算规则表（可选，用于动态配置）
    op.create_table(
        'calculation_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(128), unique=True, nullable=False),
        sa.Column('calculation_type', sa.String(32), nullable=False),
        
        # 触发条件
        sa.Column('triggers', sa.JSON, default=[]),
        
        # 输入参数
        sa.Column('required_inputs', sa.JSON, default=[]),
        sa.Column('optional_inputs', sa.JSON, default=[]),
        sa.Column('default_values', sa.JSON, default={}),
        
        # 计算逻辑
        sa.Column('formula', sa.Text),
        sa.Column('output_template', sa.Text),
        
        # 适用场景
        sa.Column('scenario_ids', sa.JSON, default=[]),
        
        # 元数据
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 参数定义表（用于标准化参数名称和单位）
    op.create_table(
        'parameter_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(64), unique=True, nullable=False),
        sa.Column('display_name', sa.String(128)),
        sa.Column('description', sa.Text),
        
        # 参数属性
        sa.Column('param_type', sa.String(32)),  # performance/spec/price/scope
        sa.Column('data_type', sa.String(32)),   # float/int/string/range
        sa.Column('unit', sa.String(32)),
        sa.Column('unit_aliases', sa.JSON, default=[]),
        
        # 值域
        sa.Column('min_value', sa.Float),
        sa.Column('max_value', sa.Float),
        sa.Column('default_value', sa.Float),
        
        # 别名（用于识别）
        sa.Column('aliases', sa.JSON, default=[]),
        
        # 适用场景
        sa.Column('scenario_ids', sa.JSON, default=[]),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # 创建索引
    op.create_index(
        'ix_feedback_records_created_at',
        'feedback_records',
        ['created_at']
    )
    op.create_index(
        'ix_feedback_records_intent_scenario',
        'feedback_records',
        ['intent_type', 'scenario_id']
    )
    op.create_index(
        'ix_conversation_contexts_updated_at',
        'conversation_contexts',
        ['updated_at']
    )


def downgrade() -> None:
    op.drop_table('parameter_definitions')
    op.drop_table('calculation_rules')
    op.drop_table('feedback_records')
    op.drop_table('conversation_contexts')

