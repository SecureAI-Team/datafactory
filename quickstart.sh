#!/bin/bash
#===============================================================================
# AI Data Factory - 快速启动脚本
# 用法: curl -sSL https://raw.githubusercontent.com/.../quickstart.sh | bash
# 或者: DASHSCOPE_API_KEY=sk-xxx bash quickstart.sh
#===============================================================================

set -e

echo ""
echo "========================================"
echo "   AI Data Factory 快速启动"
echo "========================================"
echo ""

# 获取公网 IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo "公网 IP: $PUBLIC_IP"

# 检查 API Key
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo ""
    echo "⚠️  请提供阿里云百炼 API Key"
    echo ""
    read -p "DASHSCOPE_API_KEY: " DASHSCOPE_API_KEY
    
    if [ -z "$DASHSCOPE_API_KEY" ]; then
        echo "错误: API Key 不能为空"
        exit 1
    fi
fi

# 安装目录
INSTALL_DIR="/opt/datafactory"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 克隆或更新代码
if [ -d ".git" ]; then
    echo "更新代码..."
    git pull
else
    echo "请先将代码复制到 $INSTALL_DIR"
    echo "或者使用 git clone"
    exit 1
fi

# 创建 .env 文件
cat > .env << EOF
# AI Data Factory 配置
# 生成时间: $(date)

POSTGRES_USER=adf
POSTGRES_PASSWORD=adfpass$(openssl rand -hex 4)
POSTGRES_DB=adf

MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=minio$(openssl rand -hex 4)
MINIO_URL=http://minio:9000

OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=knowledge_units
OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin123

JWT_SECRET=$(openssl rand -hex 32)

# LLM 配置
DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
UPSTREAM_LLM_API_KEY=${DASHSCOPE_API_KEY}
UPSTREAM_LLM_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEFAULT_MODEL=qwen-plus

# Langfuse (部署后获取)
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_API_KEY=

# n8n
N8N_WEBHOOK_URL=http://${PUBLIC_IP}:5678/

# Nginx
BASIC_AUTH_USER=admin
BASIC_AUTH_PASS=admin$(openssl rand -hex 4)

GATEWAY_SCENARIO_DEFAULT=sales_qa
EOF

echo "✓ 配置文件已生成"

# 运行部署脚本
chmod +x deploy.sh
bash deploy.sh

echo ""
echo "========================================"
echo "   🎉 快速启动完成！"
echo "========================================"
echo ""
echo "访问 Chat: http://${PUBLIC_IP}:3001"
echo ""

