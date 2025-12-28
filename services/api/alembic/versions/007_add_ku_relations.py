"""add ku type, relations and product fields

Revision ID: 007
Revises: 006
Create Date: 2025-12-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # 为 knowledge_units 表添加新字段
    op.add_column('knowledge_units', sa.Column('ku_type', sa.String(20), server_default='core'))
    op.add_column('knowledge_units', sa.Column('parent_ku_id', sa.String(50), nullable=True))
    op.add_column('knowledge_units', sa.Column('product_id', sa.String(100), nullable=True))
    op.add_column('knowledge_units', sa.Column('is_primary', sa.Boolean(), server_default='false'))
    op.add_column('knowledge_units', sa.Column('merge_source_ids', JSONB, server_default='[]'))
    op.add_column('knowledge_units', sa.Column('industry_tags', JSONB, server_default='[]'))
    op.add_column('knowledge_units', sa.Column('use_case_tags', JSONB, server_default='[]'))
    
    # 创建索引
    op.create_index('idx_ku_type', 'knowledge_units', ['ku_type'])
    op.create_index('idx_ku_product_id', 'knowledge_units', ['product_id'])
    op.create_index('idx_ku_parent_id', 'knowledge_units', ['parent_ku_id'])
    
    # 创建 ku_relations 表
    op.create_table(
        'ku_relations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_ku_id', sa.String(50), nullable=False),
        sa.Column('target_ku_id', sa.String(50), nullable=False),
        sa.Column('relation_type', sa.String(30), nullable=False),  # parent_of, related_to, merged_from, supersedes
        sa.Column('relation_metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ku_relations_source', 'ku_relations', ['source_ku_id'])
    op.create_index('idx_ku_relations_target', 'ku_relations', ['target_ku_id'])
    op.create_index('idx_ku_relations_type', 'ku_relations', ['relation_type'])
    
    # 创建 products 表用于产品维度管理
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.Column('primary_ku_id', sa.Integer(), nullable=True),
        sa.Column('extra_data', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_products_product_id', 'products', ['product_id'])
    op.create_index('idx_products_category', 'products', ['category'])
    
    # 创建 dedup_groups 表用于重复检测结果
    op.create_table(
        'dedup_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.String(50), unique=True, nullable=False),
        sa.Column('ku_ids', JSONB, nullable=False),  # 该组包含的 KU IDs
        sa.Column('similarity_score', sa.Float()),
        sa.Column('status', sa.String(20), server_default='pending'),  # pending, merged, dismissed
        sa.Column('merge_result_ku_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by', sa.String(100)),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_dedup_groups_status', 'dedup_groups', ['status'])


def downgrade():
    # 删除 dedup_groups 表
    op.drop_index('idx_dedup_groups_status')
    op.drop_table('dedup_groups')
    
    # 删除 products 表
    op.drop_index('idx_products_category')
    op.drop_index('idx_products_product_id')
    op.drop_table('products')
    
    # 删除 ku_relations 表
    op.drop_index('idx_ku_relations_type')
    op.drop_index('idx_ku_relations_target')
    op.drop_index('idx_ku_relations_source')
    op.drop_table('ku_relations')
    
    # 删除 knowledge_units 表的新字段
    op.drop_index('idx_ku_parent_id')
    op.drop_index('idx_ku_product_id')
    op.drop_index('idx_ku_type')
    op.drop_column('knowledge_units', 'use_case_tags')
    op.drop_column('knowledge_units', 'industry_tags')
    op.drop_column('knowledge_units', 'merge_source_ids')
    op.drop_column('knowledge_units', 'is_primary')
    op.drop_column('knowledge_units', 'product_id')
    op.drop_column('knowledge_units', 'parent_ku_id')
    op.drop_column('knowledge_units', 'ku_type')

