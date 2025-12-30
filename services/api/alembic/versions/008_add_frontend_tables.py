"""add frontend tables: users, conversations, contributions, configs

Revision ID: 008
Revises: 007
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # ==================== 用户与认证 ====================
    
    # 用户表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(100), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100)),
        sa.Column('avatar_url', sa.String(255)),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),  # admin/data_ops/bd_sales/user
        sa.Column('department', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])
    
    # 角色权限表
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('permissions', JSONB, server_default='[]'),  # ['read:ku', 'write:ku', 'admin:users']
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 用户会话表 (JWT Token 管理)
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('device_info', JSONB),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_user_sessions_user', 'user_sessions', ['user_id'])
    op.create_index('idx_user_sessions_token', 'user_sessions', ['token_hash'])
    
    # ==================== 对话管理 ====================
    
    # 扩展现有 conversations 表，添加新字段
    # 注意：现有表已有 id, channel, user_id, scenario_id, started_at, ended_at
    op.add_column('conversations', sa.Column('conversation_id', sa.String(50), unique=True))
    op.add_column('conversations', sa.Column('title', sa.String(200)))
    op.add_column('conversations', sa.Column('summary', sa.Text()))
    op.add_column('conversations', sa.Column('status', sa.String(20), server_default='active'))  # active/archived/deleted
    op.add_column('conversations', sa.Column('is_pinned', sa.Boolean(), server_default='false'))
    op.add_column('conversations', sa.Column('message_count', sa.Integer(), server_default='0'))
    op.add_column('conversations', sa.Column('last_message_at', sa.DateTime(timezone=True)))
    op.add_column('conversations', sa.Column('tags', JSONB, server_default='[]'))
    op.add_column('conversations', sa.Column('conv_metadata', JSONB, server_default='{}'))
    op.add_column('conversations', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    
    op.create_index('idx_conversations_conv_id', 'conversations', ['conversation_id'])
    op.create_index('idx_conversations_status', 'conversations', ['status'])
    op.create_index('idx_conversations_updated', 'conversations', ['updated_at'])
    
    # 对话消息表
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.String(50), nullable=False),
        sa.Column('message_id', sa.String(50), unique=True, nullable=False),
        sa.Column('role', sa.String(20), nullable=False),  # user/assistant/system
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('retrieved_context', JSONB),  # 检索到的 KU 列表
        sa.Column('sources', JSONB, server_default='[]'),  # 来源引用
        sa.Column('feedback', sa.String(10)),  # positive/negative
        sa.Column('feedback_text', sa.Text()),
        sa.Column('tokens_used', sa.Integer()),
        sa.Column('model_used', sa.String(50)),
        sa.Column('latency_ms', sa.Integer()),
        sa.Column('msg_metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_conv_messages_conv', 'conversation_messages', ['conversation_id'])
    op.create_index('idx_conv_messages_created', 'conversation_messages', ['created_at'])
    
    # 对话分享表
    op.create_table(
        'conversation_shares',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.String(50), nullable=False),
        sa.Column('share_token', sa.String(100), unique=True, nullable=False),
        sa.Column('shared_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('allow_copy', sa.Boolean(), server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('view_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_conv_shares_token', 'conversation_shares', ['share_token'])
    
    # ==================== 配置管理 ====================
    
    # 场景配置表
    op.create_table(
        'scenario_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scenario_id', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('icon', sa.String(50)),
        sa.Column('intent_patterns', JSONB, server_default='[]'),
        sa.Column('retrieval_config', JSONB, server_default='{}'),
        sa.Column('response_template', sa.Text()),
        sa.Column('quick_commands', JSONB, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_scenario_configs_id', 'scenario_configs', ['scenario_id'])
    
    # Prompt 模板表
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),  # system/user/intent/response/summary
        sa.Column('scenario_id', sa.String(50)),  # NULL 表示通用
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('variables', JSONB, server_default='[]'),
        sa.Column('version', sa.Integer(), server_default='1'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_prompt_templates_type', 'prompt_templates', ['type'])
    op.create_index('idx_prompt_templates_scenario', 'prompt_templates', ['scenario_id'])
    
    # Prompt 版本历史
    op.create_table(
        'prompt_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prompt_id', sa.Integer(), sa.ForeignKey('prompt_templates.id', ondelete='CASCADE')),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('change_reason', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_prompt_history_prompt', 'prompt_history', ['prompt_id'])
    
    # ==================== KU 类型定义 ====================
    
    op.create_table(
        'ku_type_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type_code', sa.String(50), unique=True, nullable=False),
        sa.Column('category', sa.String(30), nullable=False),  # product/solution/case/quote/biz/delivery/field
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('merge_strategy', sa.String(20), server_default='independent'),  # smart_merge/independent/append
        sa.Column('requires_expiry', sa.Boolean(), server_default='false'),
        sa.Column('requires_approval', sa.Boolean(), server_default='true'),
        sa.Column('visibility_default', sa.String(20), server_default='internal'),
        sa.Column('icon', sa.String(50)),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ku_type_defs_code', 'ku_type_definitions', ['type_code'])
    op.create_index('idx_ku_type_defs_category', 'ku_type_definitions', ['category'])
    
    # ==================== 贡献管理 ====================
    
    # 贡献记录表
    op.create_table(
        'contributions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contributor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('contribution_type', sa.String(30), nullable=False),  # file_upload/draft_ku/feedback/correction
        sa.Column('title', sa.String(200)),
        sa.Column('description', sa.Text()),
        
        # 文件上传相关
        sa.Column('file_name', sa.String(255)),
        sa.Column('file_path', sa.String(500)),
        sa.Column('file_size', sa.Integer()),
        sa.Column('mime_type', sa.String(100)),
        
        # 内容相关
        sa.Column('content_json', JSONB),
        sa.Column('ku_type_code', sa.String(50)),
        sa.Column('product_id', sa.String(100)),
        
        # 元数据
        sa.Column('tags', JSONB, server_default='[]'),
        sa.Column('visibility', sa.String(20), server_default='internal'),  # public/internal/confidential
        sa.Column('expiry_date', sa.Date()),
        
        # 触发上下文
        sa.Column('trigger_type', sa.String(30)),  # missing_info/improve_response/high_value_signal
        sa.Column('conversation_id', sa.String(50)),
        sa.Column('query_text', sa.Text()),
        
        # 状态
        sa.Column('status', sa.String(20), server_default='pending'),  # pending/processing/approved/rejected/merged
        sa.Column('processed_ku_id', sa.Integer()),
        
        # 审核
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('review_comment', sa.Text()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_contributions_contributor', 'contributions', ['contributor_id'])
    op.create_index('idx_contributions_status', 'contributions', ['status'])
    op.create_index('idx_contributions_type', 'contributions', ['contribution_type'])
    
    # 贡献统计表
    op.create_table(
        'contribution_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('total_contributions', sa.Integer(), server_default='0'),
        sa.Column('approved_count', sa.Integer(), server_default='0'),
        sa.Column('rejected_count', sa.Integer(), server_default='0'),
        sa.Column('pending_count', sa.Integer(), server_default='0'),
        sa.Column('citation_count', sa.Integer(), server_default='0'),
        sa.Column('achievements', JSONB, server_default='[]'),
        sa.Column('streak_days', sa.Integer(), server_default='0'),
        sa.Column('last_contribution_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 引用记录表
    op.create_table(
        'citation_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ku_id', sa.Integer(), sa.ForeignKey('knowledge_units.id')),
        sa.Column('contribution_id', sa.Integer(), sa.ForeignKey('contributions.id')),
        sa.Column('cited_in_conversation', sa.String(50)),
        sa.Column('cited_by_user', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_citation_records_ku', 'citation_records', ['ku_id'])
    
    # ==================== 任务协作 ====================
    
    op.create_table(
        'collaboration_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_type', sa.String(30), nullable=False),  # request_info/verify_content/approve_term/review_ku
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        
        # 关联对象
        sa.Column('related_type', sa.String(30)),  # ku/contribution/term/prompt
        sa.Column('related_id', sa.Integer()),
        
        # 分配
        sa.Column('assignee_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('requester_id', sa.Integer(), sa.ForeignKey('users.id')),
        
        # 状态
        sa.Column('status', sa.String(20), server_default='open'),  # open/in_progress/resolved/cancelled
        sa.Column('priority', sa.String(10), server_default='normal'),  # low/normal/high/urgent
        
        # 结果
        sa.Column('resolution', sa.Text()),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        
        sa.Column('due_date', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_collab_tasks_assignee', 'collaboration_tasks', ['assignee_id'])
    op.create_index('idx_collab_tasks_status', 'collaboration_tasks', ['status'])
    
    # ==================== 初始化数据 ====================
    
    # 插入默认角色
    op.execute("""
        INSERT INTO roles (name, permissions, description) VALUES
        ('admin', '["*"]', '系统管理员，拥有所有权限'),
        ('data_ops', '["read:*", "write:ku", "write:config", "review:*"]', '数据运维，负责KU管理和审核'),
        ('bd_sales', '["read:ku", "write:contribution", "read:config"]', 'BD/销售，使用问答和贡献材料'),
        ('user', '["read:ku", "write:contribution"]', '普通用户');
    """)
    
    # 插入 KU 类型定义
    op.execute("""
        INSERT INTO ku_type_definitions (type_code, category, display_name, merge_strategy, requires_expiry, sort_order) VALUES
        -- 产品与技术类
        ('core.product_feature', 'product', '产品功能说明', 'smart_merge', false, 10),
        ('core.tech_spec', 'product', '技术规格', 'smart_merge', false, 11),
        ('core.delivery_guide', 'product', '实施指南', 'smart_merge', false, 12),
        ('core.integration', 'product', 'API/集成文档', 'smart_merge', false, 13),
        ('core.release_notes', 'product', '版本说明', 'independent', true, 14),
        -- 解决方案与售前
        ('solution.industry', 'solution', '行业解决方案', 'smart_merge', false, 20),
        ('solution.proposal', 'solution', '方案书', 'independent', false, 21),
        ('solution.poc', 'solution', 'PoC方案', 'independent', false, 22),
        ('sales.competitor', 'sales', '竞品分析', 'independent', false, 23),
        ('sales.playbook', 'sales', '销售话术', 'smart_merge', false, 24),
        -- 案例与证据类
        ('case.customer_story', 'case', '客户案例', 'independent', false, 30),
        ('case.public_reference', 'case', '公开证据', 'independent', false, 31),
        -- 商务与交易类
        ('quote.pricebook', 'quote', '报价单', 'independent', true, 40),
        ('biz.contract_sla', 'biz', '合同/SLA', 'independent', false, 41),
        ('bid.rfp_response', 'biz', '投标材料', 'independent', false, 42),
        ('compliance.certification', 'biz', '资质认证', 'independent', true, 43),
        -- 交付与运营类
        ('delivery.sop', 'delivery', '交付SOP', 'smart_merge', false, 50),
        ('support.troubleshooting', 'delivery', '故障排查', 'smart_merge', false, 51),
        ('enablement.training', 'delivery', '培训材料', 'smart_merge', false, 52),
        -- 过程型增量
        ('field.signal', 'field', '现场信号', 'independent', false, 60),
        ('eval.dataset', 'field', '评测数据', 'append', false, 61);
    """)
    
    # 插入默认管理员用户 (密码: admin123，使用 bcrypt hash)
    # 注意：生产环境应该修改此密码
    op.execute("""
        INSERT INTO users (username, email, password_hash, display_name, role, is_active) VALUES
        ('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.O5O5O5O5O5O5Ou', '系统管理员', 'admin', true);
    """)


def downgrade():
    # 删除表（按依赖关系逆序）
    op.drop_table('collaboration_tasks')
    op.drop_table('citation_records')
    op.drop_table('contribution_stats')
    op.drop_table('contributions')
    op.drop_table('ku_type_definitions')
    op.drop_table('prompt_history')
    op.drop_table('prompt_templates')
    op.drop_table('scenario_configs')
    op.drop_table('conversation_shares')
    op.drop_table('conversation_messages')
    
    # 删除 conversations 表的新增字段
    op.drop_index('idx_conversations_updated')
    op.drop_index('idx_conversations_status')
    op.drop_index('idx_conversations_conv_id')
    op.drop_column('conversations', 'updated_at')
    op.drop_column('conversations', 'conv_metadata')
    op.drop_column('conversations', 'tags')
    op.drop_column('conversations', 'last_message_at')
    op.drop_column('conversations', 'message_count')
    op.drop_column('conversations', 'is_pinned')
    op.drop_column('conversations', 'status')
    op.drop_column('conversations', 'summary')
    op.drop_column('conversations', 'title')
    op.drop_column('conversations', 'conversation_id')
    
    op.drop_table('user_sessions')
    op.drop_table('roles')
    op.drop_table('users')

