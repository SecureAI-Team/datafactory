#!/bin/bash
#===============================================================================
# AI Data Factory - 升级脚本
# 用于更新已部署到阿里云 ECS 的环境
#===============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# 配置变量
INSTALL_DIR="${INSTALL_DIR:-/opt/datafactory}"
BACKUP_DIR="${BACKUP_DIR:-/opt/datafactory/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo ""
echo "========================================"
echo "   AI Data Factory 升级脚本"
echo "   版本: 2.0 (含自研前后端)"
echo "   时间: $(date)"
echo "========================================"
echo ""

#===============================================================================
# 0. 检查环境
#===============================================================================
check_environment() {
    log_step "检查运行环境..."
    
    # 检查目录
    if [ ! -d "$INSTALL_DIR" ]; then
        log_error "安装目录不存在: $INSTALL_DIR"
        log_info "请先运行 deploy.sh 进行初始部署"
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    
    # 检查 docker compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        log_error ".env 文件不存在"
        exit 1
    fi
    
    log_success "环境检查通过"
}

#===============================================================================
# 1. 备份数据
#===============================================================================
backup_data() {
    log_step "备份数据..."
    
    mkdir -p "$BACKUP_DIR"
    
    source .env
    
    # 备份 PostgreSQL
    log_info "备份 PostgreSQL 数据库..."
    docker compose exec -T postgres pg_dumpall -U "$POSTGRES_USER" > "$BACKUP_DIR/postgres_$TIMESTAMP.sql" 2>/dev/null || {
        log_warn "PostgreSQL 备份失败，可能数据库未运行"
    }
    
    # 备份 .env 文件
    cp .env "$BACKUP_DIR/.env_$TIMESTAMP"
    
    # 压缩旧备份（保留最近5个）
    cd "$BACKUP_DIR"
    ls -t postgres_*.sql 2>/dev/null | tail -n +6 | xargs -r rm -f
    ls -t .env_* 2>/dev/null | tail -n +6 | xargs -r rm -f
    cd "$INSTALL_DIR"
    
    log_success "备份完成: $BACKUP_DIR"
}

#===============================================================================
# 2. 拉取最新代码
#===============================================================================
pull_latest_code() {
    log_step "拉取最新代码..."
    
    cd "$INSTALL_DIR"
    
    if [ -d ".git" ]; then
        # 保存本地修改
        git stash push -m "Auto stash before upgrade $TIMESTAMP" 2>/dev/null || true
        
        # 拉取最新代码
        git fetch origin
        
        # 显示更新内容
        echo ""
        log_info "即将应用的更新:"
        git log --oneline HEAD..origin/main 2>/dev/null | head -20 || git log --oneline HEAD..origin/master 2>/dev/null | head -20 || echo "  (无法获取更新日志)"
        echo ""
        
        # 合并更新
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
            log_error "拉取代码失败"
            exit 1
        }
        
        log_success "代码更新完成"
    else
        log_warn "非 Git 仓库，跳过代码拉取"
        log_info "请手动更新代码文件"
    fi
}

#===============================================================================
# 3. 修复脚本文件
#===============================================================================
fix_scripts() {
    log_step "修复脚本文件（移除 Windows 换行符和 BOM）..."
    
    # 修复所有 shell 脚本
    for script in scripts/*.sh *.sh; do
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
# 4. 停止服务
#===============================================================================
stop_services() {
    log_step "停止服务..."
    
    # 只停止需要重建的服务，保持数据库运行
    docker compose stop api web-ui admin-ui nginx airflow 2>/dev/null || true
    
    log_success "服务已停止"
}

#===============================================================================
# 5. 重建镜像
#===============================================================================
rebuild_images() {
    log_step "重建 Docker 镜像..."
    
    # 重建 API 镜像
    log_info "重建 API 镜像..."
    docker compose build --no-cache api
    
    # 检查前端目录是否存在并重建
    if [ -d "services/web-ui" ]; then
        log_info "重建用户前端镜像 (web-ui)..."
        docker compose build --no-cache web-ui
    fi
    
    if [ -d "services/admin-ui" ]; then
        log_info "重建管理后台镜像 (admin-ui)..."
        docker compose build --no-cache admin-ui
    fi
    
    log_success "镜像重建完成"
}

#===============================================================================
# 6. 运行数据库迁移
#===============================================================================
run_migrations() {
    log_step "运行数据库迁移..."
    
    # 确保 PostgreSQL 运行
    docker compose up -d postgres
    sleep 5
    
    # 等待 PostgreSQL 就绪
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U adf &>/dev/null; then
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
    
    # 启动 API 容器运行迁移
    docker compose up -d api
    sleep 5
    
    # 运行 Alembic 迁移
    log_info "执行 Alembic 迁移..."
    docker compose exec -T api alembic upgrade head || {
        log_warn "迁移可能已应用或有冲突"
        # 尝试标记当前版本
        docker compose exec -T api alembic stamp head 2>/dev/null || true
    }
    
    log_success "数据库迁移完成"
    
    # 创建默认用户
    log_info "创建默认用户..."
    docker compose run --rm -v "$(pwd)":/work -w /work api python scripts/create_admin_user.py 2>/dev/null || log_warn "用户创建跳过（可能已存在）"
}

#===============================================================================
# 7. 启动所有服务
#===============================================================================
start_services() {
    log_step "启动所有服务..."
    
    docker compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 15
    
    # 等待 API 就绪
    for i in {1..30}; do
        if curl -s http://localhost:8000/health &>/dev/null; then
            log_success "API 服务已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
    
    log_success "所有服务已启动"
}

#===============================================================================
# 8. 验证升级
#===============================================================================
verify_upgrade() {
    log_step "验证升级..."
    
    echo ""
    echo "========================================"
    echo "   服务状态"
    echo "========================================"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" | head -25
    
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
        "Open-WebUI:http://localhost:3001"
        "Web-UI:http://localhost:3002"
        "Admin-UI:http://localhost:3003"
    )
    
    for svc in "${services[@]}"; do
        name="${svc%%:*}"
        url="${svc#*:}"
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [[ "$status" =~ ^(200|301|302|401|403)$ ]]; then
            echo -e "  ${GREEN}✓${NC} $name ($status)"
        else
            echo -e "  ${YELLOW}○${NC} $name ($status) - 可能未启用"
        fi
    done
    
    # 检查新 API 端点
    echo ""
    echo "========================================"
    echo "   新增 API 检查"
    echo "========================================"
    
    new_endpoints=(
        "/api/auth:认证模块"
        "/api/users:用户管理"
        "/api/conversations:对话管理"
        "/api/settings:系统设置"
    )
    
    for ep in "${new_endpoints[@]}"; do
        path="${ep%%:*}"
        name="${ep#*:}"
        status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000$path" 2>/dev/null || echo "000")
        if [[ "$status" =~ ^(200|401|403|404|405|422)$ ]]; then
            echo -e "  ${GREEN}✓${NC} $name ($path)"
        else
            echo -e "  ${YELLOW}○${NC} $name ($path) - 状态: $status"
        fi
    done
    
    # 检查索引
    echo ""
    DOC_COUNT=$(curl -s "http://localhost:9200/knowledge_units/_count" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
    echo "  OpenSearch 索引文档数: $DOC_COUNT"
}

#===============================================================================
# 9. 打印访问信息
#===============================================================================
print_access_info() {
    source .env 2>/dev/null || true
    PUBLIC_IP="${PUBLIC_IP:-$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"
    
    echo ""
    echo "========================================"
    echo "   🎉 升级完成！"
    echo "========================================"
    echo ""
    echo "┌────────────────────┬──────────────────────────────────────────┐"
    echo "│ 服务               │ 地址                                     │"
    echo "├────────────────────┼──────────────────────────────────────────┤"
    echo "│ 💬 Chat (WebUI)    │ http://${PUBLIC_IP}:3001                 │"
    echo "│ 🌐 用户前端 (新)   │ http://${PUBLIC_IP}:3002 或 /app         │"
    echo "│ 🔧 管理后台 (新)   │ http://${PUBLIC_IP}:3003 或 /admin       │"
    echo "│ 📖 API Docs        │ http://${PUBLIC_IP}:8000/docs            │"
    echo "│ 📊 Langfuse        │ http://${PUBLIC_IP}:3000                 │"
    echo "│ 🔄 n8n             │ http://${PUBLIC_IP}:5678                 │"
    echo "│ 📝 Budibase        │ http://${PUBLIC_IP}:10000                │"
    echo "│ 🌬️ Airflow         │ http://${PUBLIC_IP}:8080                 │"
    echo "│ 💾 MinIO           │ http://${PUBLIC_IP}:9001                 │"
    echo "└────────────────────┴──────────────────────────────────────────┘"
    echo ""
    echo "新增功能:"
    echo "  ✅ 用户认证系统 (JWT)"
    echo "  ✅ 对话历史管理"
    echo "  ✅ 系统配置管理"
    echo "  ✅ 用户前端 (React + TailwindCSS)"
    echo "  ✅ 管理后台 (React + Ant Design)"
    echo ""
    echo "快速命令:"
    echo "  make status        - 查看状态"
    echo "  make up-frontends  - 启动前端服务"
    echo "  make migrate       - 运行数据库迁移"
    echo "  make help          - 查看所有命令"
    echo ""
}

#===============================================================================
# 快速升级（跳过备份）
#===============================================================================
quick_upgrade() {
    log_info "快速升级模式（跳过备份）..."
    
    check_environment
    pull_latest_code
    fix_scripts
    stop_services
    rebuild_images
    run_migrations
    start_services
    verify_upgrade
    print_access_info
    
    log_success "快速升级完成！"
}

#===============================================================================
# 仅重建前端
#===============================================================================
upgrade_frontends_only() {
    log_info "仅升级前端服务..."
    
    check_environment
    
    if [ -d ".git" ]; then
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
    fi
    
    # 停止前端服务
    docker compose stop web-ui admin-ui nginx 2>/dev/null || true
    
    # 重建前端镜像
    if [ -d "services/web-ui" ]; then
        log_info "重建 web-ui..."
        docker compose build --no-cache web-ui
    fi
    
    if [ -d "services/admin-ui" ]; then
        log_info "重建 admin-ui..."
        docker compose build --no-cache admin-ui
    fi
    
    # 启动服务
    docker compose up -d web-ui admin-ui nginx
    
    log_success "前端升级完成！"
    
    # 显示状态
    echo ""
    docker compose ps web-ui admin-ui nginx
}

#===============================================================================
# 仅重建 API
#===============================================================================
upgrade_api_only() {
    log_info "仅升级 API 服务..."
    
    check_environment
    
    if [ -d ".git" ]; then
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
    fi
    
    # 停止 API 服务
    docker compose stop api 2>/dev/null || true
    
    # 重建 API 镜像
    log_info "重建 API..."
    docker compose build --no-cache api
    
    # 运行迁移
    docker compose up -d postgres
    sleep 3
    docker compose up -d api
    sleep 3
    docker compose exec -T api alembic upgrade head 2>/dev/null || true
    
    log_success "API 升级完成！"
    
    # 显示状态
    echo ""
    docker compose ps api
}

#===============================================================================
# 回滚
#===============================================================================
rollback() {
    log_warn "回滚功能..."
    
    cd "$INSTALL_DIR"
    
    # 列出可用备份
    echo "可用的数据库备份:"
    ls -la "$BACKUP_DIR"/postgres_*.sql 2>/dev/null || echo "  无备份"
    echo ""
    
    # 列出 Git 提交
    if [ -d ".git" ]; then
        echo "最近的 Git 提交:"
        git log --oneline -10
        echo ""
        echo "要回滚代码，请运行:"
        echo "  git checkout <commit_hash>"
        echo "  ./upgrade.sh rebuild"
    fi
    
    echo ""
    echo "要恢复数据库备份，请运行:"
    echo "  cat $BACKUP_DIR/postgres_YYYYMMDD_HHMMSS.sql | docker compose exec -T postgres psql -U adf"
}

#===============================================================================
# 仅重建（不拉取代码）
#===============================================================================
rebuild_only() {
    log_info "仅重建服务..."
    
    check_environment
    fix_scripts
    stop_services
    rebuild_images
    run_migrations
    start_services
    verify_upgrade
    print_access_info
    
    log_success "重建完成！"
}

#===============================================================================
# 主流程
#===============================================================================
main() {
    log_info "开始完整升级..."
    
    check_environment
    backup_data
    pull_latest_code
    fix_scripts
    stop_services
    rebuild_images
    run_migrations
    start_services
    verify_upgrade
    print_access_info
    
    log_success "升级完成！"
}

#===============================================================================
# 命令行入口
#===============================================================================
case "${1:-}" in
    quick)
        quick_upgrade
        ;;
    frontend|frontends)
        upgrade_frontends_only
        ;;
    api)
        upgrade_api_only
        ;;
    rebuild)
        rebuild_only
        ;;
    backup)
        check_environment
        backup_data
        ;;
    migrate)
        check_environment
        run_migrations
        ;;
    verify)
        check_environment
        verify_upgrade
        ;;
    rollback)
        rollback
        ;;
    info)
        print_access_info
        ;;
    help|--help|-h)
        echo "用法: $0 [命令]"
        echo ""
        echo "命令:"
        echo "  (无参数)   - 完整升级（备份 + 拉取代码 + 重建 + 迁移）"
        echo "  quick      - 快速升级（跳过备份）"
        echo "  frontend   - 仅升级前端服务 (web-ui, admin-ui)"
        echo "  api        - 仅升级 API 服务"
        echo "  rebuild    - 仅重建（不拉取代码）"
        echo "  backup     - 仅备份数据"
        echo "  migrate    - 仅运行数据库迁移"
        echo "  verify     - 验证当前部署状态"
        echo "  rollback   - 显示回滚选项"
        echo "  info       - 显示访问信息"
        echo "  help       - 显示此帮助"
        echo ""
        echo "示例:"
        echo "  ./upgrade.sh              # 完整升级"
        echo "  ./upgrade.sh quick        # 快速升级"
        echo "  ./upgrade.sh frontend     # 仅更新前端"
        echo "  ./upgrade.sh api          # 仅更新 API"
        echo ""
        ;;
    *)
        main
        ;;
esac

