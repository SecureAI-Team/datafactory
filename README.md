# AI Data Factory (single-VM, docker-compose)

一站式 AI 数据工厂：文档处理 → 知识提取 → RAG 对话

## 🚀 一键部署 (阿里云 ECS)

```bash
# 1. SSH 登录 ECS
ssh root@YOUR_ECS_IP

# 2. 下载代码到 /opt/datafactory
mkdir -p /opt/datafactory && cd /opt/datafactory
# (上传或 git clone 代码)

# 3. 一键部署
chmod +x deploy.sh
DASHSCOPE_API_KEY=sk-你的百炼Key bash deploy.sh

# 部署完成后访问:
# Chat: http://YOUR_IP:3001
# API:  http://YOUR_IP:8000/docs
```

## 🔧 手动部署

```bash
# 1. 克隆并配置
git clone https://github.com/yourorg/ai-data-factory.git
cd ai-data-factory
cp .env.example .env

# 2. 编辑 .env 配置 API Key
# DASHSCOPE_API_KEY=sk-xxxxx  # 阿里云百炼 API Key

# 3. 启动服务
make init up

# 4. 查看状态
make status
```

## 📍 服务访问地址

直接端口访问（推荐）:

| 服务 | 地址 | 说明 |
|------|------|------|
| 💬 Chat (Open WebUI) | http://IP:3001 | AI 对话界面 |
| 🔧 API Docs | http://IP:8000/docs | FastAPI 文档 |
| 📊 Langfuse | http://IP:3000 | LLM 追踪 |
| 🔄 n8n | http://IP:5678 | 自动化工作流 |
| 📝 Budibase | http://IP:10000 | 贡献门户 |
| 🌬️ Airflow | http://IP:8080 | Pipeline 编排 |
| 💾 MinIO Console | http://IP:9001 | 对象存储 |
| 🔍 OpenSearch | http://IP:9200 | 搜索引擎 |
| 📚 OpenMetadata | http://IP:8585 | 数据治理 |

## 🔑 默认账户

| 服务 | 用户名 | 密码 |
|------|--------|------|
| Airflow | admin | admin123 |
| MinIO | minio | minio123 |
| Budibase | admin@example.com | admin |
| Langfuse | 首次注册创建 | - |
| n8n | 首次注册创建 | - |

## 📦 Make 命令

```bash
# 基础操作
make up        # 启动所有服务
make down      # 停止服务
make logs      # 查看日志
make status    # 查看状态

# 初始化
make init      # 初始化数据库、存储
make setup     # 服务配置向导 (Langfuse/n8n/Budibase)

# Pipeline 操作
make pipeline         # 触发完整 Pipeline
make pipeline-ingest  # 仅运行 ingest (uploads → bronze)
make pipeline-extract # 仅运行 extract (bronze → silver)
make pipeline-expand  # 仅运行 expand (silver → gold)
make pipeline-index   # 仅运行 index (gold → OpenSearch)

# 验证和调试
make verify       # 验证 RAG 流程
make smoke        # 健康检查
make buckets      # 查看 MinIO 内容
make index-status # 查看索引状态

# 开发
make test      # 运行测试
make lint      # 代码检查
make reset     # 重置所有数据 (危险!)
make help      # 查看所有命令
```

## 🔄 数据流程

```
用户上传文档
    ↓
MinIO: uploads/
    ↓ [ingest_to_bronze DAG]
MinIO: bronze/raw/
    ↓ [extract_to_silver DAG - Tika/Unstructured 文本提取]
MinIO: silver/extracted/
    ↓ [expand_and_rewrite_to_gold DAG - LLM 结构化重写]
MinIO: gold/knowledge_units/
    ↓ [index_to_opensearch DAG]
OpenSearch: knowledge_units 索引
    ↓
RAG Gateway: 检索 + LLM 生成
    ↓
Open WebUI: 用户对话
```

## 🛠️ 手动 Pipeline 测试

```bash
# 1. 上传测试文件到 MinIO
docker run --rm --network datafactory_default --entrypoint sh \
  minio/mc:latest -c "
    mc alias set m http://minio:9000 minio minio123 &&
    echo 'RESTful API 设计指南...' | mc pipe m/uploads/test.txt
  "

# 2. 运行 Pipeline 各阶段
make pipeline-ingest
make pipeline-extract
make pipeline-expand
make pipeline-index

# 3. 验证索引
curl -s "http://localhost:9200/knowledge_units/_count"

# 4. 测试 RAG 对话
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-plus", "messages": [{"role": "user", "content": "什么是 RESTful？"}]}'
```

## 📊 Langfuse 追踪配置

1. 访问 http://IP:3000/ 注册账户
2. 创建项目 `ai-data-factory`
3. 在 Settings → API Keys 创建密钥
4. 配置到 `.env`:
   ```
   LANGFUSE_HOST=http://langfuse:3000
   LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
   LANGFUSE_API_KEY=sk-lf-xxxxxxxx
   ```
5. 重启 API: `docker compose restart api`
6. 发送对话后在 Langfuse Traces 中查看

## 🔧 服务架构

- **FastAPI** - 核心 API (ingest, KU, retrieval, gateway)
- **Airflow** - Pipeline 编排 (bronze→silver→gold→index)
- **MinIO** - 对象存储 (uploads/bronze/silver/gold)
- **OpenSearch** - 向量/文本检索
- **Tika + Unstructured** - 文档解析
- **Langfuse** - LLM 追踪和 Prompt 管理
- **Open WebUI** - 用户聊天界面
- **Budibase** - 低代码贡献门户
- **n8n** - 自动化工作流
- **OpenMetadata** - 数据目录和治理

## 📋 资源需求

推荐配置: 8 vCPU / 16GB RAM
最低配置: 4 vCPU / 8GB RAM (禁用部分服务)

禁用可选服务:
```bash
# 在 .env 中设置
DISABLE_BUDIBASE=1
DISABLE_OPENMETADATA=1
DISABLE_LANGFUSE=1
```

## 🔐 安全说明

- Open WebUI 通过 Nginx 反向代理，可配置 Basic Auth
- API 支持 JWT 认证，角色: `DATA_OPS`, `BD_SALES`
- 生产环境请配置 HTTPS 和强密码
- 修改 `.env` 中的默认密码

## 📚 更多文档

- `docs/runbook_pipeline_triad.md` - Pipeline 运维手册
- `docs/runbook_search_tuning.md` - 搜索调优指南
- `docs/sop_add_prompt.md` - Prompt 管理 SOP
