"""add system configs, LLM providers, and env mapping

Revision ID: 009
Revises: 008
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # ==================== 系统配置表 ====================
    
    op.create_table(
        'system_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('config_group', sa.String(50), nullable=False),  # llm/search/storage/pipeline/notification/security
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('config_value', sa.Text()),
        sa.Column('value_type', sa.String(20), server_default='string'),  # string/number/boolean/json/secret
        sa.Column('description', sa.Text()),
        sa.Column('is_secret', sa.Boolean(), server_default='false'),
        sa.Column('is_editable', sa.Boolean(), server_default='true'),
        sa.Column('validation_rule', JSONB),
        sa.Column('default_value', sa.Text()),
        sa.Column('source', sa.String(20), server_default='database'),  # env/database/synced
        sa.Column('env_var_name', sa.String(100)),  # 对应的环境变量名
        sa.Column('is_bootstrap', sa.Boolean(), server_default='false'),  # 是否启动必需配置
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('config_group', 'config_key', name='uq_system_configs_group_key'),
    )
    op.create_index('idx_system_configs_group', 'system_configs', ['config_group'])
    
    # 配置变更历史
    op.create_table(
        'config_change_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('config_id', sa.Integer(), sa.ForeignKey('system_configs.id', ondelete='CASCADE')),
        sa.Column('old_value', sa.Text()),
        sa.Column('new_value', sa.Text()),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('change_reason', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_config_logs_config', 'config_change_logs', ['config_id'])
    
    # ==================== LLM 配置表 ====================
    
    # LLM 提供商表
    op.create_table(
        'llm_providers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_code', sa.String(50), unique=True, nullable=False),  # qwen/openai/azure/local
        sa.Column('provider_name', sa.String(100), nullable=False),
        sa.Column('api_base_url', sa.String(500)),
        sa.Column('api_key_encrypted', sa.Text()),  # 加密存储
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('config', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # LLM 模型列表
    op.create_table(
        'llm_models',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('llm_providers.id', ondelete='CASCADE')),
        sa.Column('model_code', sa.String(100), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('model_type', sa.String(30), nullable=False),  # chat/embedding/vision/audio
        sa.Column('capabilities', JSONB, server_default='[]'),  # ['text', 'vision', 'function_call']
        sa.Column('context_window', sa.Integer()),
        sa.Column('max_output_tokens', sa.Integer()),
        sa.Column('cost_per_1k_input', sa.Numeric(10, 6)),
        sa.Column('cost_per_1k_output', sa.Numeric(10, 6)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('config', JSONB, server_default='{}'),  # temperature, top_p 等默认值
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('provider_id', 'model_code', name='uq_llm_models_provider_code'),
    )
    op.create_index('idx_llm_models_provider', 'llm_models', ['provider_id'])
    
    # 模型使用场景映射
    op.create_table(
        'llm_model_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('use_case', sa.String(50), unique=True, nullable=False),  # chat/expand/summary/intent/embedding/vision
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('llm_models.id')),
        sa.Column('fallback_model_id', sa.Integer(), sa.ForeignKey('llm_models.id')),
        sa.Column('priority', sa.Integer(), server_default='0'),
        sa.Column('config_override', JSONB, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_llm_assignments_use_case', 'llm_model_assignments', ['use_case'])
    
    # ==================== 配置映射表 ====================
    
    op.create_table(
        'config_env_mapping',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('env_var_name', sa.String(100), unique=True, nullable=False),
        sa.Column('config_group', sa.String(50), nullable=False),
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('transform_rule', sa.String(50)),  # none/decrypt/parse_json
        sa.Column('is_secret', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # ==================== 初始化 LLM 配置数据 ====================
    
    # 插入 LLM 提供商
    op.execute("""
        INSERT INTO llm_providers (provider_code, provider_name, api_base_url, is_default, is_active) VALUES
        ('qwen', '阿里云百炼 Qwen', 'https://dashscope.aliyuncs.com/compatible-mode/v1', true, true),
        ('openai', 'OpenAI', 'https://api.openai.com/v1', false, true),
        ('azure', 'Azure OpenAI', '', false, false),
        ('local', '本地模型', 'http://localhost:11434/v1', false, false);
    """)
    
    # 插入 LLM 模型
    op.execute("""
        INSERT INTO llm_models (provider_id, model_code, model_name, model_type, capabilities, context_window, is_default) VALUES
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'qwen-max', 'Qwen Max', 'chat', '["text", "function_call"]', 32000, true),
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'qwen-plus', 'Qwen Plus', 'chat', '["text"]', 131072, false),
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'qwen-turbo', 'Qwen Turbo', 'chat', '["text"]', 131072, false),
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'qwen-long', 'Qwen Long', 'chat', '["text", "long_context"]', 1000000, false),
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'qwen-vl-max', 'Qwen VL Max', 'vision', '["text", "vision"]', 32000, false),
        ((SELECT id FROM llm_providers WHERE provider_code = 'qwen'), 'text-embedding-v3', 'Text Embedding V3', 'embedding', '["embedding"]', 8192, false);
    """)
    
    # 插入模型使用场景分配
    op.execute("""
        INSERT INTO llm_model_assignments (use_case, model_id) VALUES
        ('chat', (SELECT id FROM llm_models WHERE model_code = 'qwen-max')),
        ('expand', (SELECT id FROM llm_models WHERE model_code = 'qwen-plus')),
        ('summary', (SELECT id FROM llm_models WHERE model_code = 'qwen-long')),
        ('intent', (SELECT id FROM llm_models WHERE model_code = 'qwen-turbo')),
        ('embedding', (SELECT id FROM llm_models WHERE model_code = 'text-embedding-v3')),
        ('vision', (SELECT id FROM llm_models WHERE model_code = 'qwen-vl-max'));
    """)
    
    # ==================== 初始化系统配置数据 ====================
    
    op.execute("""
        INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, is_secret, env_var_name, is_bootstrap) VALUES
        -- LLM 通用配置
        ('llm', 'default_temperature', '0.7', 'number', 'LLM 默认温度参数', false, 'LLM_TEMPERATURE', false),
        ('llm', 'default_max_tokens', '2048', 'number', 'LLM 默认最大输出 Token', false, 'LLM_MAX_TOKENS', false),
        ('llm', 'request_timeout', '60', 'number', 'LLM 请求超时时间(秒)', false, NULL, false),
        ('llm', 'retry_attempts', '3', 'number', 'LLM 请求失败重试次数', false, NULL, false),
        ('llm', 'rate_limit_rpm', '60', 'number', '每分钟最大请求数', false, NULL, false),
        
        -- 检索配置
        ('search', 'default_top_k', '5', 'number', '默认返回结果数', false, NULL, false),
        ('search', 'min_score_threshold', '0.3', 'number', '最小相关性分数阈值', false, NULL, false),
        ('search', 'bm25_weight', '0.3', 'number', 'BM25 权重', false, NULL, false),
        ('search', 'vector_weight', '0.7', 'number', '向量检索权重', false, NULL, false),
        ('search', 'enable_hybrid_search', 'true', 'boolean', '是否启用混合检索', false, NULL, false),
        ('search', 'rerank_enabled', 'false', 'boolean', '是否启用重排序', false, NULL, false),
        ('search', 'chunk_size', '512', 'number', '文档分块大小', false, NULL, false),
        ('search', 'chunk_overlap', '50', 'number', '分块重叠大小', false, NULL, false),
        
        -- 存储配置
        ('storage', 'max_upload_size_mb', '50', 'number', '最大上传文件大小(MB)', false, NULL, false),
        ('storage', 'allowed_file_types', '["pdf","docx","doc","pptx","ppt","xlsx","xls","txt","md","csv"]', 'json', '允许上传的文件类型', false, NULL, false),
        ('storage', 'minio_bucket_uploads', 'uploads', 'string', 'MinIO 上传桶名', false, NULL, false),
        ('storage', 'minio_bucket_bronze', 'bronze', 'string', 'MinIO Bronze 层桶名', false, NULL, false),
        ('storage', 'minio_bucket_silver', 'silver', 'string', 'MinIO Silver 层桶名', false, NULL, false),
        ('storage', 'minio_bucket_gold', 'gold', 'string', 'MinIO Gold 层桶名', false, NULL, false),
        ('storage', 'file_retention_days', '365', 'number', '文件保留天数', false, NULL, false),
        
        -- Pipeline 配置
        ('pipeline', 'auto_trigger_on_upload', 'true', 'boolean', '上传后自动触发 Pipeline', false, NULL, false),
        ('pipeline', 'batch_size', '10', 'number', '批处理大小', false, NULL, false),
        ('pipeline', 'parallel_workers', '4', 'number', '并行处理数', false, NULL, false),
        ('pipeline', 'expand_enabled', 'true', 'boolean', '是否启用 LLM 扩展', false, NULL, false),
        ('pipeline', 'dq_gate_enabled', 'true', 'boolean', '是否启用 DQ 门禁', false, NULL, false),
        ('pipeline', 'auto_publish', 'false', 'boolean', '是否自动发布（跳过审核）', false, NULL, false),
        
        -- 安全配置
        ('security', 'jwt_expire_hours', '24', 'number', 'JWT Token 过期时间(小时)', false, NULL, false),
        ('security', 'jwt_refresh_days', '7', 'number', 'Refresh Token 过期时间(天)', false, NULL, false),
        ('security', 'password_min_length', '8', 'number', '密码最小长度', false, NULL, false),
        ('security', 'login_max_attempts', '5', 'number', '登录最大尝试次数', false, NULL, false),
        ('security', 'lockout_duration_minutes', '30', 'number', '账户锁定时长(分钟)', false, NULL, false),
        ('security', 'session_timeout_minutes', '60', 'number', '会话超时时间(分钟)', false, NULL, false),
        ('security', 'enable_audit_log', 'true', 'boolean', '是否启用审计日志', false, NULL, false),
        
        -- 系统配置
        ('system', 'app_name', 'AI 数据工厂', 'string', '应用名称', false, NULL, false),
        ('system', 'app_logo_url', '/logo.png', 'string', '应用 Logo URL', false, NULL, false),
        ('system', 'maintenance_mode', 'false', 'boolean', '维护模式', false, NULL, false),
        ('system', 'registration_enabled', 'false', 'boolean', '是否允许注册', false, NULL, false),
        ('system', 'default_user_role', 'bd_sales', 'string', '新用户默认角色', false, NULL, false),
        ('system', 'timezone', 'Asia/Shanghai', 'string', '系统时区', false, NULL, false),
        ('system', 'language', 'zh-CN', 'string', '系统语言', false, NULL, false),
        
        -- 功能开关
        ('feature', 'enable_vision', 'true', 'boolean', '启用多模态识别', false, NULL, false),
        ('feature', 'enable_knowledge_graph', 'true', 'boolean', '启用知识图谱', false, NULL, false),
        ('feature', 'enable_recommendation', 'true', 'boolean', '启用智能推荐', false, NULL, false),
        ('feature', 'enable_dialogue_summary', 'true', 'boolean', '启用对话摘要', false, NULL, false),
        ('feature', 'enable_calculation', 'true', 'boolean', '启用计算引擎', false, NULL, false),
        ('feature', 'enable_contribution', 'true', 'boolean', '启用用户贡献', false, NULL, false),
        ('feature', 'enable_feedback_optimization', 'true', 'boolean', '启用反馈优化', false, NULL, false),
        
        -- 集成配置 (启动必需)
        ('integration', 'opensearch_url', 'http://opensearch:9200', 'string', 'OpenSearch URL', false, 'OPENSEARCH_URL', true),
        ('integration', 'minio_endpoint', 'minio:9000', 'string', 'MinIO 端点', false, 'MINIO_ENDPOINT', true),
        ('integration', 'minio_access_key', 'minio', 'string', 'MinIO Access Key', false, 'MINIO_ACCESS_KEY', true),
        ('integration', 'minio_secret_key', '', 'secret', 'MinIO Secret Key', true, 'MINIO_SECRET_KEY', true),
        ('integration', 'redis_url', 'redis://redis:6379/0', 'string', 'Redis URL', false, 'REDIS_URL', true),
        ('integration', 'neo4j_url', 'bolt://neo4j:7687', 'string', 'Neo4j URL', false, 'NEO4J_URI', true),
        ('integration', 'neo4j_user', 'neo4j', 'string', 'Neo4j 用户名', false, 'NEO4J_USER', true),
        ('integration', 'neo4j_password', '', 'secret', 'Neo4j 密码', true, 'NEO4J_PASSWORD', true),
        ('integration', 'langfuse_enabled', 'true', 'boolean', '启用 Langfuse 追踪', false, NULL, false),
        ('integration', 'langfuse_host', 'http://langfuse:3000', 'string', 'Langfuse URL', false, 'LANGFUSE_HOST', false);
    """)
    
    # ==================== 初始化配置映射 ====================
    
    op.execute("""
        INSERT INTO config_env_mapping (env_var_name, config_group, config_key, is_secret) VALUES
        -- LLM 配置
        ('DASHSCOPE_API_KEY', 'llm_provider', 'qwen.api_key', true),
        ('OPENAI_API_KEY', 'llm_provider', 'openai.api_key', true),
        ('LLM_TEMPERATURE', 'llm', 'default_temperature', false),
        ('LLM_MAX_TOKENS', 'llm', 'default_max_tokens', false),
        
        -- MinIO 配置
        ('MINIO_ENDPOINT', 'integration', 'minio_endpoint', false),
        ('MINIO_ACCESS_KEY', 'integration', 'minio_access_key', false),
        ('MINIO_SECRET_KEY', 'integration', 'minio_secret_key', true),
        
        -- OpenSearch 配置
        ('OPENSEARCH_URL', 'integration', 'opensearch_url', false),
        ('OPENSEARCH_INDEX', 'search', 'default_index', false),
        
        -- PostgreSQL 配置（启动必需，只读）
        ('POSTGRES_HOST', 'bootstrap', 'postgres_host', false),
        ('POSTGRES_PORT', 'bootstrap', 'postgres_port', false),
        ('POSTGRES_USER', 'bootstrap', 'postgres_user', false),
        ('POSTGRES_PASSWORD', 'bootstrap', 'postgres_password', true),
        ('POSTGRES_DB', 'bootstrap', 'postgres_db', false),
        
        -- Redis 配置
        ('REDIS_URL', 'integration', 'redis_url', false),
        
        -- Neo4j 配置
        ('NEO4J_URI', 'integration', 'neo4j_url', false),
        ('NEO4J_USER', 'integration', 'neo4j_user', false),
        ('NEO4J_PASSWORD', 'integration', 'neo4j_password', true),
        
        -- Langfuse 配置
        ('LANGFUSE_HOST', 'integration', 'langfuse_host', false),
        ('LANGFUSE_PUBLIC_KEY', 'integration', 'langfuse_public_key', false),
        ('LANGFUSE_SECRET_KEY', 'integration', 'langfuse_secret_key', true);
    """)


def downgrade():
    op.drop_table('config_env_mapping')
    op.drop_table('llm_model_assignments')
    op.drop_table('llm_models')
    op.drop_table('llm_providers')
    op.drop_table('config_change_logs')
    op.drop_table('system_configs')

