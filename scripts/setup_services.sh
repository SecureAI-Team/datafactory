#!/bin/bash
# =============================================================================
# AI Data Factory - 服务初始化脚本
# 自动化配置 Langfuse, n8n, Budibase 等服务
# =============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 获取服务器公网IP
PUBLIC_IP="${PUBLIC_IP:-$(curl -s ifconfig.me 2>/dev/null || echo 'localhost')}"
log_info "检测到公网IP: $PUBLIC_IP"

# =============================================================================
# 1. 等待服务就绪
# =============================================================================
wait_for_service() {
    local name=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    log_info "等待 $name 就绪..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -qE "^(200|301|302|401|403)"; then
            log_success "$name 已就绪"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    log_warn "$name 未能在 $((max_attempts * 2)) 秒内就绪"
    return 1
}

# =============================================================================
# 2. Langfuse 配置
# =============================================================================
setup_langfuse() {
    log_info "========== 配置 Langfuse =========="
    
    LANGFUSE_URL="http://localhost:3000"
    
    if ! wait_for_service "Langfuse" "$LANGFUSE_URL" 30; then
        log_error "Langfuse 服务未运行"
        return 1
    fi
    
    echo ""
    log_info "Langfuse 配置说明:"
    echo "  1. 打开浏览器访问: http://${PUBLIC_IP}:3000/"
    echo "  2. 点击 'Sign Up' 创建账户"
    echo "  3. 输入邮箱: admin@example.com"
    echo "  4. 设置密码: admin123"
    echo "  5. 登录后点击 'New Project' 创建项目: ai-data-factory"
    echo "  6. 进入项目 Settings -> API Keys -> Create API Key"
    echo "  7. 复制 Public Key 和 Secret Key"
    echo ""
    
    # 检查是否已配置
    if [ -n "$LANGFUSE_PUBLIC_KEY" ] && [ -n "$LANGFUSE_API_KEY" ]; then
        log_success "Langfuse API Keys 已配置"
        echo "  LANGFUSE_PUBLIC_KEY: $LANGFUSE_PUBLIC_KEY"
    else
        log_warn "请配置 Langfuse API Keys 到 .env 文件:"
        echo "  LANGFUSE_HOST=http://langfuse:3000"
        echo "  LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx"
        echo "  LANGFUSE_API_KEY=sk-lf-xxxxxxxx"
    fi
    
    echo ""
}

# =============================================================================
# 3. n8n 配置
# =============================================================================
setup_n8n() {
    log_info "========== 配置 n8n =========="
    
    N8N_URL="http://localhost:5678"
    
    if ! wait_for_service "n8n" "$N8N_URL" 30; then
        log_error "n8n 服务未运行"
        return 1
    fi
    
    echo ""
    log_info "n8n 配置说明:"
    echo "  1. 打开浏览器访问: http://${PUBLIC_IP}:5678/"
    echo "  2. 首次访问需要创建账户"
    echo "  3. 输入邮箱和密码完成注册"
    echo ""
    log_info "推荐创建的工作流:"
    echo "  - 📄 文档上传通知: Webhook 触发 -> Slack/邮件通知"
    echo "  - ⏰ 定时 Pipeline: Schedule -> HTTP Request 触发 Airflow DAG"
    echo "  - 📊 质量检查告警: Webhook -> 条件判断 -> 通知"
    echo ""
    
    # 创建示例工作流文件
    mkdir -p workflows
    cat > workflows/n8n_document_notification.json << 'EOF'
{
  "name": "Document Upload Notification",
  "nodes": [
    {
      "parameters": {
        "path": "document-uploaded",
        "options": {}
      },
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300]
    },
    {
      "parameters": {
        "channel": "#data-factory",
        "text": "=📄 新文档已上传: {{ $json.filename }}\n上传者: {{ $json.uploader }}\n时间: {{ $now }}"
      },
      "name": "Slack",
      "type": "n8n-nodes-base.slack",
      "position": [500, 300]
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Slack", "type": "main", "index": 0}]]
    }
  }
}
EOF
    log_success "示例工作流已保存到 workflows/n8n_document_notification.json"
    echo ""
}

# =============================================================================
# 4. Budibase 配置
# =============================================================================
setup_budibase() {
    log_info "========== 配置 Budibase =========="
    
    BUDIBASE_URL="http://localhost:10000"
    
    if ! wait_for_service "Budibase" "$BUDIBASE_URL" 30; then
        log_error "Budibase 服务未运行"
        return 1
    fi
    
    echo ""
    log_info "Budibase 配置说明:"
    echo "  1. 打开浏览器访问: http://${PUBLIC_IP}:10000/"
    echo "  2. 使用默认管理员账户登录:"
    echo "     邮箱: admin@example.com"
    echo "     密码: admin"
    echo "  3. 创建 '文档贡献门户' 应用"
    echo ""
    log_info "推荐创建的应用:"
    echo "  - 📤 文档上传表单: 文件上传 + 元数据输入"
    echo "  - 📋 审批工作台: 待审核文档列表 + 审批操作"
    echo "  - 📊 统计仪表盘: 文档数量、处理状态等"
    echo ""
}

# =============================================================================
# 5. 生成环境配置模板
# =============================================================================
generate_env_template() {
    log_info "========== 生成环境配置 =========="
    
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_success "已从 .env.example 创建 .env"
        fi
    fi
    
    # 追加 Langfuse 配置模板
    if ! grep -q "LANGFUSE_PUBLIC_KEY" .env 2>/dev/null; then
        cat >> .env << EOF

# Langfuse 追踪配置 (从 Langfuse Web UI 获取)
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_API_KEY=
EOF
        log_info "已添加 Langfuse 配置模板到 .env"
    fi
    
    echo ""
}

# =============================================================================
# 6. 打印服务访问信息
# =============================================================================
print_access_info() {
    echo ""
    log_info "=========================================="
    log_info "       AI Data Factory 服务访问地址"
    log_info "=========================================="
    echo ""
    echo "┌──────────────────┬────────────────────────────────────────┐"
    echo "│ 服务             │ 地址                                   │"
    echo "├──────────────────┼────────────────────────────────────────┤"
    echo "│ 💬 Chat (WebUI)  │ http://${PUBLIC_IP}/                   │"
    echo "│ 📊 Langfuse      │ http://${PUBLIC_IP}:3000/              │"
    echo "│ 🔄 n8n           │ http://${PUBLIC_IP}:5678/              │"
    echo "│ 📝 Budibase      │ http://${PUBLIC_IP}:10000/             │"
    echo "│ 🌬️ Airflow       │ http://${PUBLIC_IP}:8080/              │"
    echo "│ 💾 MinIO         │ http://${PUBLIC_IP}:9001/              │"
    echo "│ 🔍 OpenSearch    │ http://${PUBLIC_IP}:9200/              │"
    echo "│ 📚 OpenMetadata  │ http://${PUBLIC_IP}:8585/              │"
    echo "│ 🔧 API Docs      │ http://${PUBLIC_IP}:8000/docs          │"
    echo "└──────────────────┴────────────────────────────────────────┘"
    echo ""
    log_info "默认账户信息:"
    echo "  Airflow:    admin / admin123"
    echo "  MinIO:      \$MINIO_ROOT_USER / \$MINIO_ROOT_PASSWORD"
    echo "  Budibase:   admin@example.com / admin"
    echo "  Langfuse:   首次注册创建"
    echo "  n8n:        首次注册创建"
    echo ""
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    echo ""
    log_info "=========================================="
    log_info "    AI Data Factory 服务初始化脚本"
    log_info "=========================================="
    echo ""
    
    # 加载环境变量
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    generate_env_template
    setup_langfuse
    setup_n8n
    setup_budibase
    print_access_info
    
    log_success "服务初始化说明完成！"
    echo ""
    log_info "下一步操作:"
    echo "  1. 按照上述说明在浏览器中完成各服务的首次配置"
    echo "  2. 配置 Langfuse API Keys 到 .env 文件"
    echo "  3. 重启 API 服务以启用追踪: docker compose restart api"
    echo "  4. 在 Open WebUI 中测试对话，然后在 Langfuse 中查看追踪"
    echo ""
}

main "$@"

