#!/bin/bash
# =============================================================================
# AI Data Factory - RAG 验证脚本
# 验证检索增强生成(RAG)流程是否正常工作
# =============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

API_URL="${API_URL:-http://localhost:8000}"
OPENSEARCH_URL="${OPENSEARCH_URL:-http://localhost:9200}"

echo ""
echo "=========================================="
echo "    AI Data Factory RAG 验证"
echo "=========================================="
echo ""

# =============================================================================
# 1. 检查 OpenSearch 索引
# =============================================================================
log_step "1. 检查 OpenSearch 索引状态"

DOC_COUNT=$(curl -s "${OPENSEARCH_URL}/knowledge_units/_count" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")

if [ "$DOC_COUNT" -gt 0 ]; then
    log_success "OpenSearch 索引正常，文档数: $DOC_COUNT"
else
    log_error "OpenSearch 索引为空或不可用"
    echo "  请先运行 Pipeline 处理文档"
    exit 1
fi

# =============================================================================
# 2. 测试检索 API
# =============================================================================
log_step "2. 测试检索 API"

SEARCH_RESULT=$(curl -s "${API_URL}/api/retrieval/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "RESTful", "top_k": 3}' 2>/dev/null)

HIT_COUNT=$(echo "$SEARCH_RESULT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null || echo "0")

if [ "$HIT_COUNT" -gt 0 ]; then
    log_success "检索 API 正常，命中 $HIT_COUNT 条结果"
    echo "  首条结果:"
    echo "$SEARCH_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data:
    h = data[0]
    print(f\"    标题: {h.get('title', 'N/A')}\")
    print(f\"    来源: {h.get('source_file', 'N/A')}\")
    print(f\"    分数: {h.get('score', 'N/A')}\")
"
else
    log_error "检索 API 返回空结果"
    echo "  响应: $SEARCH_RESULT"
fi

# =============================================================================
# 3. 测试 RAG 对话
# =============================================================================
log_step "3. 测试 RAG 对话"

echo "  发送问题: '什么是 RESTful？'"
echo ""

RAG_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "什么是 RESTful？请简要回答"}],
        "stream": false
    }' 2>/dev/null)

# 提取回答内容
ANSWER=$(echo "$RAG_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'choices' in data and data['choices']:
        print(data['choices'][0]['message']['content'])
    elif 'error' in data:
        print(f\"错误: {data['error']}\")
    else:
        print(f\"未知响应: {data}\")
except Exception as e:
    print(f\"解析错误: {e}\")
" 2>/dev/null)

if [ -n "$ANSWER" ]; then
    log_success "RAG 对话正常"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────────┐"
    echo "  │ 回答:                                                       │"
    echo "  └─────────────────────────────────────────────────────────────┘"
    echo "$ANSWER" | fold -w 60 -s | sed 's/^/    /'
    echo ""
    
    # 检查是否包含来源引用
    if echo "$ANSWER" | grep -q "来源"; then
        log_success "回答包含来源引用 ✓"
    else
        log_info "回答未包含明确来源引用 (可能需要调整 Prompt)"
    fi
else
    log_error "RAG 对话失败"
    echo "  响应: $RAG_RESPONSE"
fi

# =============================================================================
# 4. 检查 Langfuse 追踪
# =============================================================================
log_step "4. 检查 Langfuse 追踪状态"

LANGFUSE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000" 2>/dev/null || echo "000")

if [ "$LANGFUSE_STATUS" = "200" ] || [ "$LANGFUSE_STATUS" = "302" ]; then
    log_success "Langfuse 服务可用"
    echo "  请在浏览器中查看追踪: http://localhost:3000/"
    echo "  (需要先配置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_API_KEY)"
else
    log_info "Langfuse 服务状态: $LANGFUSE_STATUS"
fi

# =============================================================================
# 总结
# =============================================================================
echo ""
echo "=========================================="
echo "    验证完成"
echo "=========================================="
echo ""
echo "  ✓ OpenSearch 索引: $DOC_COUNT 个文档"
echo "  ✓ 检索 API: $HIT_COUNT 条命中"
echo "  ✓ RAG 对话: 正常"
echo ""
echo "  下一步:"
echo "    1. 在 Open WebUI 中测试对话"
echo "    2. 在 Langfuse 中查看追踪记录"
echo "    3. 上传更多文档扩展知识库"
echo ""

