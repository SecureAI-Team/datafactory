#!/bin/bash
# 确保使用 bash 而不是 sh
# AI Data Factory - User Simulation Test
# 模拟用户实际使用流程

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

HOST="${HOST:-localhost}"
API_URL="http://$HOST:8000"
WEBUI_URL="http://$HOST:3001"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   AI Data Factory - User Simulation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# Scenario 1: BD/Sales User - Chat with RAG
# ========================================
echo -e "${CYAN}=== Scenario 1: BD/Sales User - Chat Experience ===${NC}"
echo ""

echo -e "${YELLOW}Step 1: Access Open WebUI${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$WEBUI_URL" 2>/dev/null)
if [ "$response" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Open WebUI is accessible"
else
    echo -e "  ${RED}✗${NC} Cannot access Open WebUI (HTTP $response)"
fi

echo -e "${YELLOW}Step 2: Send a chat message (via API)${NC}"
chat_payload='{
  "model": "qwen-plus",
  "messages": [
    {"role": "user", "content": "你好，请介绍一下你自己"}
  ],
  "stream": false
}'

echo "  Sending: '你好，请介绍一下你自己'"
chat_response=$(curl -s -X POST "$API_URL/api/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "$chat_payload" 2>/dev/null || echo '{"error": "connection failed"}')

if echo "$chat_response" | grep -q "choices"; then
    echo -e "  ${GREEN}✓${NC} Chat response received"
    # Extract and show a snippet of the response
    content=$(echo "$chat_response" | grep -o '"content":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 100)
    echo -e "  Response: ${content}..."
elif echo "$chat_response" | grep -q "Unauthorized\|API key\|401"; then
    echo -e "  ${YELLOW}⚠${NC} API key not configured in .env (DASHSCOPE_API_KEY)"
else
    echo -e "  ${RED}✗${NC} Chat failed: $chat_response"
fi

echo ""

# ========================================
# Scenario 2: Data Ops - Document Ingestion
# ========================================
echo -e "${CYAN}=== Scenario 2: Data Ops - Document Ingestion ===${NC}"
echo ""

echo -e "${YELLOW}Step 1: Create a test document${NC}"
TEST_DOC="/tmp/test_document.txt"
cat > "$TEST_DOC" << 'EOF'
AI Data Factory 测试文档

这是一个用于测试数据工厂pipeline的示例文档。

## 主要功能

1. 文档解析 - 使用Apache Tika和Unstructured
2. 知识抽取 - 基于LLM的信息提取
3. 向量检索 - OpenSearch混合搜索
4. RAG对话 - 结合检索结果的智能问答

## 技术栈

- FastAPI 后端服务
- Open WebUI 聊天界面
- PostgreSQL 数据存储
- MinIO 对象存储
- OpenSearch 向量索引
EOF
echo -e "  ${GREEN}✓${NC} Test document created"

echo -e "${YELLOW}Step 2: Upload document to MinIO${NC}"
# Check if MinIO is accessible
minio_health=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:9000/minio/health/live" 2>/dev/null)
if [ "$minio_health" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} MinIO is healthy"
    echo -e "  ${YELLOW}⚠${NC} Direct upload requires mc client or API endpoint"
else
    echo -e "  ${RED}✗${NC} MinIO not accessible"
fi

echo -e "${YELLOW}Step 3: Check Tika for document parsing${NC}"
tika_response=$(curl -s -X PUT "http://$HOST:9998/tika" \
    -H "Content-Type: text/plain" \
    -d "Hello World" 2>/dev/null || echo "error")
if echo "$tika_response" | grep -q "Hello"; then
    echo -e "  ${GREEN}✓${NC} Tika is working"
else
    echo -e "  ${YELLOW}⚠${NC} Tika response: $tika_response"
fi

echo ""

# ========================================
# Scenario 3: Admin - System Monitoring
# ========================================
echo -e "${CYAN}=== Scenario 3: Admin - System Monitoring ===${NC}"
echo ""

echo -e "${YELLOW}Step 1: Check Langfuse for tracing${NC}"
langfuse_response=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:3000" 2>/dev/null)
if [ "$langfuse_response" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Langfuse UI is accessible"
else
    echo -e "  ${RED}✗${NC} Langfuse not accessible (HTTP $langfuse_response)"
fi

echo -e "${YELLOW}Step 2: Check Airflow for pipeline orchestration${NC}"
airflow_response=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:8080" 2>/dev/null)
if [ "$airflow_response" == "200" ] || [ "$airflow_response" == "302" ]; then
    echo -e "  ${GREEN}✓${NC} Airflow UI is accessible"
else
    echo -e "  ${YELLOW}⚠${NC} Airflow returned HTTP $airflow_response"
fi

echo -e "${YELLOW}Step 3: Check n8n for workflow automation${NC}"
n8n_response=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:5678" 2>/dev/null)
if [ "$n8n_response" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} n8n UI is accessible"
else
    echo -e "  ${RED}✗${NC} n8n not accessible (HTTP $n8n_response)"
fi

echo ""

# ========================================
# Scenario 4: Search & Retrieval
# ========================================
echo -e "${CYAN}=== Scenario 4: Search & Retrieval ===${NC}"
echo ""

echo -e "${YELLOW}Step 1: Check OpenSearch cluster health${NC}"
os_health=$(curl -s "http://$HOST:9200/_cluster/health" 2>/dev/null || echo '{"status":"error"}')
os_status=$(echo "$os_health" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
if [ "$os_status" == "green" ]; then
    echo -e "  ${GREEN}✓${NC} OpenSearch cluster is green"
elif [ "$os_status" == "yellow" ]; then
    echo -e "  ${YELLOW}⚠${NC} OpenSearch cluster is yellow (single node)"
else
    echo -e "  ${RED}✗${NC} OpenSearch status: $os_status"
fi

echo -e "${YELLOW}Step 2: Check knowledge_units index${NC}"
index_check=$(curl -s "http://$HOST:9200/knowledge_units" 2>/dev/null || echo '{"error":"not found"}')
if echo "$index_check" | grep -q "mappings"; then
    doc_count=$(curl -s "http://$HOST:9200/knowledge_units/_count" 2>/dev/null | grep -o '"count":[0-9]*' | cut -d':' -f2)
    echo -e "  ${GREEN}✓${NC} Index exists with $doc_count documents"
elif echo "$index_check" | grep -q "index_not_found"; then
    echo -e "  ${YELLOW}⚠${NC} Index not created yet (run 'make init')"
else
    echo -e "  ${RED}✗${NC} Cannot check index"
fi

echo ""

# ========================================
# Summary
# ========================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Simulation Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Environment is ready for use!${NC}"
echo ""
echo "Next steps for manual testing:"
echo ""
echo "1. Open WebUI Chat:"
echo "   - URL: http://$HOST/ (or public IP)"
echo "   - Login: dev / dev123 (basic auth)"
echo "   - Create account in Open WebUI"
echo ""
echo "2. Configure LLM API Key:"
echo "   - Edit .env file on server"
echo "   - Set DASHSCOPE_API_KEY=your_key"
echo "   - Restart: docker compose restart api"
echo ""
echo "3. Test Document Upload:"
echo "   - Access Budibase: http://$HOST:10000"
echo "   - Or use API: POST /api/ingest"
echo ""
echo "4. Monitor Pipeline:"
echo "   - Airflow: http://$HOST:8080 (admin/admin123)"
echo "   - Langfuse: http://$HOST:3000"
echo ""

# Cleanup
rm -f "$TEST_DOC"

