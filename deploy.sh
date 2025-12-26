#!/bin/bash
#===============================================================================
# AI Data Factory - 一键部署脚本
# 适用于阿里云 ECS (Ubuntu/Debian)
#===============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置变量
INSTALL_DIR="${INSTALL_DIR:-/opt/datafactory}"
PUBLIC_IP="${PUBLIC_IP:-$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"

echo ""
echo "========================================"
echo "   AI Data Factory 一键部署"
echo "   目标目录: $INSTALL_DIR"
echo "   公网 IP: $PUBLIC_IP"
echo "========================================"
echo ""

#===============================================================================
# 1. 检查 Docker
#===============================================================================
check_docker() {
    log_info "检查 Docker 环境..."
    
    if ! command -v docker &> /dev/null; then
        log_warn "Docker 未安装，正在安装..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        log_success "Docker 安装完成"
    else
        log_success "Docker 已安装: $(docker --version)"
    fi
    
    # 检查 docker compose
    if ! docker compose version &> /dev/null; then
        log_warn "Docker Compose 插件未安装，正在安装..."
        apt-get update && apt-get install -y docker-compose-plugin
    fi
    log_success "Docker Compose 已就绪"
}

#===============================================================================
# 2. 创建目录和配置
#===============================================================================
setup_project() {
    log_info "设置项目目录..."
    
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # 如果是从 git 克隆
    if [ -d ".git" ]; then
        log_info "更新代码..."
        git pull
    fi
    
    log_success "项目目录已就绪: $INSTALL_DIR"
}

#===============================================================================
# 3. 生成环境配置
#===============================================================================
create_env() {
    log_info "生成环境配置文件..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# ========================================
# AI Data Factory 环境配置
# 生成时间: $(date)
# ========================================

# PostgreSQL
POSTGRES_USER=adf
POSTGRES_PASSWORD=adfpass$(openssl rand -hex 4)
POSTGRES_DB=adf
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# MinIO
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=minio$(openssl rand -hex 4)
MINIO_URL=http://minio:9000

# OpenSearch
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=knowledge_units
OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin123

# JWT
JWT_SECRET=$(openssl rand -hex 32)
JWT_ALGO=HS256

# LLM (阿里云百炼 Qwen)
UPSTREAM_LLM_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=
UPSTREAM_LLM_API_KEY=\${DASHSCOPE_API_KEY}
DEFAULT_MODEL=qwen-plus

# Langfuse (可选，部署后在 Web UI 获取)
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_API_KEY=

# n8n
N8N_WEBHOOK_URL=http://${PUBLIC_IP}:5678/

# Nginx Basic Auth (用于保护 Chat 入口)
BASIC_AUTH_USER=admin
BASIC_AUTH_PASS=admin$(openssl rand -hex 4)

# Gateway
GATEWAY_SCENARIO_DEFAULT=sales_qa
EOF
        log_success "已生成 .env 文件"
        log_warn "请编辑 .env 文件，填入 DASHSCOPE_API_KEY"
    else
        log_info ".env 文件已存在，跳过生成"
    fi
}

#===============================================================================
# 4. 创建必要的目录和文件
#===============================================================================
create_dirs() {
    log_info "创建必要的目录..."
    
    mkdir -p infra/nginx/certs
    mkdir -p services/dq/uncommitted/data_docs
    mkdir -p services/api/static
    mkdir -p workflows
    
    # 创建 .htpasswd 文件
    if [ ! -f "infra/nginx/.htpasswd" ]; then
        source .env 2>/dev/null || true
        BASIC_AUTH_USER="${BASIC_AUTH_USER:-admin}"
        BASIC_AUTH_PASS="${BASIC_AUTH_PASS:-admin123}"
        
        docker run --rm --entrypoint htpasswd httpd:2 -Bbn "$BASIC_AUTH_USER" "$BASIC_AUTH_PASS" > infra/nginx/.htpasswd
        log_success "已生成 .htpasswd 文件"
    fi
    
    log_success "目录创建完成"
}

#===============================================================================
# 5. 启动基础服务
#===============================================================================
start_base_services() {
    log_info "启动基础服务 (postgres, minio, opensearch)..."
    
    docker compose up -d postgres minio opensearch redis
    
    log_info "等待服务就绪..."
    sleep 15
    
    # 等待 PostgreSQL
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U adf &>/dev/null; then
            log_success "PostgreSQL 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # 等待 OpenSearch
    for i in {1..30}; do
        if curl -s http://localhost:9200 &>/dev/null; then
            log_success "OpenSearch 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # 等待 MinIO
    for i in {1..30}; do
        if curl -s http://localhost:9000/minio/health/live &>/dev/null; then
            log_success "MinIO 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
}

#===============================================================================
# 6. 初始化数据库
#===============================================================================
init_databases() {
    log_info "初始化数据库..."
    
    source .env
    
    # 重要：设置 PostgreSQL 用户密码（因为 PostgreSQL 只在首次启动时读取 POSTGRES_PASSWORD）
    # 这确保密码与 .env 中的配置一致
    log_info "同步 PostgreSQL 用户密码..."
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -c \
        "ALTER USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';" || true
    
    # 创建 Airflow 数据库
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -tc \
        "SELECT 1 FROM pg_database WHERE datname='airflow';" | grep -q 1 || \
        docker compose exec -T postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE airflow;"
    
    # 创建 Langfuse 数据库
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -tc \
        "SELECT 1 FROM pg_database WHERE datname='langfuse';" | grep -q 1 || \
        docker compose exec -T postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE langfuse;"
    
    # 创建 OpenMetadata 数据库
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -tc \
        "SELECT 1 FROM pg_database WHERE datname='openmetadata';" | grep -q 1 || \
        docker compose exec -T postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE openmetadata;"
    
    log_success "数据库初始化完成"
}

#===============================================================================
# 6.5 修复脚本文件
#===============================================================================
fix_scripts() {
    log_info "修复脚本文件（移除 Windows 换行符和 BOM）..."
    
    # 修复所有 shell 脚本
    for script in scripts/*.sh; do
        if [ -f "$script" ]; then
            # 移除 BOM
            sed -i '1s/^\xef\xbb\xbf//' "$script" 2>/dev/null || true
            # 移除 Windows 换行符
            sed -i 's/\r$//' "$script" 2>/dev/null || true
            chmod +x "$script"
        fi
    done
    
    log_success "脚本文件修复完成"
}

#===============================================================================
# 7. 构建和启动所有服务
#===============================================================================
start_all_services() {
    log_info "构建自定义镜像..."
    docker compose build --parallel
    
    log_info "启动所有服务..."
    docker compose up -d
    
    log_info "等待服务启动..."
    sleep 30
    
    # 等待 API 服务就绪
    log_info "等待 API 服务就绪..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health &>/dev/null; then
            log_success "API 服务已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
}

#===============================================================================
# 7.5 运行数据库迁移
#===============================================================================
run_migrations() {
    log_info "运行 API 数据库迁移 (Alembic)..."
    
    # 等待 API 容器完全启动
    sleep 5
    
    # 运行 Alembic 迁移
    docker compose exec -T api alembic upgrade head || {
        log_warn "Alembic 迁移失败，尝试初始化..."
        docker compose exec -T api alembic stamp head || true
    }
    
    log_success "数据库迁移完成"
}

#===============================================================================
# 8. 初始化 MinIO 和 OpenSearch
#===============================================================================
init_storage() {
    log_info "初始化 MinIO buckets..."
    
    source .env
    
    docker compose run --rm -v "$(pwd)":/work -w /work \
        -e MINIO_URL=http://minio:9000 \
        -e MINIO_ROOT_USER="$MINIO_ROOT_USER" \
        -e MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
        api python scripts/create_buckets.py || log_warn "Buckets 可能已存在"
    
    log_info "初始化 OpenSearch 索引..."
    
    docker compose run --rm -v "$(pwd)":/work -w /work \
        -e OPENSEARCH_URL=http://opensearch:9200 \
        -e OPENSEARCH_INDEX=knowledge_units \
        api python scripts/create_opensearch_index.py || log_warn "索引可能已存在"
    
    log_info "添加种子数据..."
    
    docker compose run --rm -v "$(pwd)":/work -w /work \
        -e MINIO_URL=http://minio:9000 \
        -e MINIO_ROOT_USER="$MINIO_ROOT_USER" \
        -e MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
        api python scripts/seed_data.py || log_warn "种子数据可能已存在"
    
    log_success "存储初始化完成"
}

#===============================================================================
# 9. 运行初始 Pipeline
#===============================================================================
run_initial_pipeline() {
    log_info "运行初始 Pipeline..."
    
    # 等待 Airflow 就绪
    for i in {1..30}; do
        if curl -s http://localhost:8080/health &>/dev/null; then
            log_success "Airflow 已就绪"
            break
        fi
        echo -n "."
        sleep 3
    done
    
    # 运行 Pipeline
    TODAY=$(date +%Y-%m-%d)
    
    log_info "运行 ingest_to_bronze..."
    docker compose exec -T airflow airflow tasks test ingest_to_bronze ingest_files "$TODAY" 2>&1 | tail -5 || true
    
    log_info "运行 extract_to_silver..."
    docker compose exec -T airflow airflow tasks test extract_to_silver extract_text "$TODAY" 2>&1 | tail -5 || true
    
    log_info "运行 expand_and_rewrite_to_gold..."
    docker compose exec -T airflow airflow tasks test expand_and_rewrite_to_gold expand_and_rewrite "$TODAY" 2>&1 | tail -5 || true
    
    log_info "运行 index_to_opensearch..."
    docker compose exec -T airflow airflow tasks test index_to_opensearch index_knowledge_units "$TODAY" 2>&1 | tail -5 || true
    
    log_success "Pipeline 运行完成"
}

#===============================================================================
# 10. 验证部署
#===============================================================================
verify_deployment() {
    log_info "验证部署..."
    
    echo ""
    echo "========================================"
    echo "   服务状态"
    echo "========================================"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" | head -20
    
    echo ""
    echo "========================================"
    echo "   健康检查"
    echo "========================================"
    
    # 检查各服务
    services=(
        "API:http://localhost:8000/health"
        "OpenSearch:http://localhost:9200"
        "MinIO:http://localhost:9001"
        "Airflow:http://localhost:8080"
        "Langfuse:http://localhost:3000"
        "Open-WebUI:http://localhost:3001"
        "n8n:http://localhost:5678"
        "Budibase:http://localhost:10000"
    )
    
    for svc in "${services[@]}"; do
        name="${svc%%:*}"
        url="${svc#*:}"
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [[ "$status" =~ ^(200|301|302|401|403)$ ]]; then
            echo -e "  ${GREEN}✓${NC} $name ($status)"
        else
            echo -e "  ${RED}✗${NC} $name ($status)"
        fi
    done
    
    # 检查索引
    echo ""
    DOC_COUNT=$(curl -s "http://localhost:9200/knowledge_units/_count" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
    echo "  OpenSearch 索引文档数: $DOC_COUNT"
}

#===============================================================================
# 11. 打印访问信息
#===============================================================================
print_access_info() {
    source .env 2>/dev/null || true
    
    echo ""
    echo "========================================"
    echo "   🎉 部署完成！"
    echo "========================================"
    echo ""
    echo "┌──────────────────┬────────────────────────────────────────┐"
    echo "│ 服务             │ 地址                                   │"
    echo "├──────────────────┼────────────────────────────────────────┤"
    echo "│ 💬 Chat (WebUI)  │ http://${PUBLIC_IP}:3001               │"
    echo "│ 🔧 API Docs      │ http://${PUBLIC_IP}:8000/docs          │"
    echo "│ 📊 Langfuse      │ http://${PUBLIC_IP}:3000               │"
    echo "│ 🔄 n8n           │ http://${PUBLIC_IP}:5678               │"
    echo "│ 📝 Budibase      │ http://${PUBLIC_IP}:10000              │"
    echo "│ 🌬️ Airflow       │ http://${PUBLIC_IP}:8080               │"
    echo "│ 💾 MinIO         │ http://${PUBLIC_IP}:9001               │"
    echo "│ 🔍 OpenSearch    │ http://${PUBLIC_IP}:9200               │"
    echo "└──────────────────┴────────────────────────────────────────┘"
    echo ""
    echo "默认账户:"
    echo "  Airflow:  admin / admin123"
    echo "  MinIO:    ${MINIO_ROOT_USER:-minio} / ${MINIO_ROOT_PASSWORD:-查看.env}"
    echo "  Budibase: admin@example.com / admin"
    echo ""
    echo "⚠️  重要提醒:"
    echo "  1. 请编辑 .env 文件，填入 DASHSCOPE_API_KEY (阿里云百炼 API Key)"
    echo "  2. 填入后重启 API: docker compose restart api airflow"
    echo "  3. 在 Langfuse 注册后，获取 API Keys 填入 .env"
    echo ""
    echo "快速命令:"
    echo "  make status   - 查看状态"
    echo "  make verify   - 验证 RAG"
    echo "  make help     - 查看所有命令"
    echo ""
}

#===============================================================================
# 主流程
#===============================================================================
main() {
    log_info "开始部署..."
    
    check_docker
    setup_project
    create_env
    create_dirs
    fix_scripts
    start_base_services
    init_databases
    start_all_services
    run_migrations
    init_storage
    
    # 检查是否配置了 API Key
    source .env 2>/dev/null || true
    if [ -n "$DASHSCOPE_API_KEY" ]; then
        run_initial_pipeline
    else
        log_warn "DASHSCOPE_API_KEY 未配置，跳过 Pipeline 运行"
    fi
    
    verify_deployment
    print_access_info
    
    log_success "部署完成！"
}

# 支持单独运行某个步骤
case "${1:-}" in
    docker)     check_docker ;;
    env)        create_env ;;
    dirs)       create_dirs ;;
    fix)        fix_scripts ;;
    base)       start_base_services ;;
    db)         init_databases ;;
    start)      start_all_services ;;
    migrate)    run_migrations ;;
    init)       init_storage ;;
    pipeline)   run_initial_pipeline ;;
    verify)     verify_deployment ;;
    info)       print_access_info ;;
    help)
        echo "用法: $0 [步骤]"
        echo ""
        echo "步骤:"
        echo "  docker    - 检查/安装 Docker"
        echo "  env       - 生成 .env 配置文件"
        echo "  dirs      - 创建必要目录"
        echo "  fix       - 修复脚本文件（BOM/换行符）"
        echo "  base      - 启动基础服务"
        echo "  db        - 初始化数据库"
        echo "  start     - 启动所有服务"
        echo "  migrate   - 运行数据库迁移"
        echo "  init      - 初始化存储（MinIO/OpenSearch）"
        echo "  pipeline  - 运行初始 Pipeline"
        echo "  verify    - 验证部署"
        echo "  info      - 显示访问信息"
        echo ""
        echo "不带参数运行完整部署流程"
        ;;
    *)          main ;;
esac

