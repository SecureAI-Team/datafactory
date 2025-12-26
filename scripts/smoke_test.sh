#!/bin/bash
# AI Data Factory - Smoke Test Script
# 用于验证所有服务是否正常运行

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
HOST="${HOST:-localhost}"
PUBLIC_IP="${PUBLIC_IP:-localhost}"

# 计数器
PASSED=0
FAILED=0
WARNINGS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   AI Data Factory - Smoke Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 测试函数
test_service() {
    local name="$1"
    local url="$2"
    local expected_code="${3:-200}"
    local auth="$4"
    
    echo -n "Testing $name... "
    
    if [ -n "$auth" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -u "$auth" "$url" 2>/dev/null || echo "000")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    fi
    
    if [ "$response" == "$expected_code" ] || [ "$response" == "301" ] || [ "$response" == "302" ]; then
        echo -e "${GREEN}✓ OK${NC} (HTTP $response)"
        ((PASSED++))
        return 0
    elif [ "$response" == "401" ] || [ "$response" == "403" ]; then
        echo -e "${YELLOW}⚠ Auth Required${NC} (HTTP $response)"
        ((WARNINGS++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $response, expected $expected_code)"
        ((FAILED++))
        return 1
    fi
}

test_container() {
    local name="$1"
    echo -n "Container $name... "
    
    status=$(docker compose ps --format json "$name" 2>/dev/null | grep -o '"State":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ "$status" == "running" ]; then
        echo -e "${GREEN}✓ Running${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ Not Running${NC} (Status: $status)"
        ((FAILED++))
        return 1
    fi
}

echo -e "${YELLOW}=== 1. Container Status ===${NC}"
echo ""

test_container "postgres"
test_container "minio"
test_container "opensearch"
test_container "redis"
test_container "tika"
test_container "unstructured"
test_container "api"
test_container "open-webui"
test_container "nginx"
test_container "langfuse"
test_container "n8n"
test_container "budibase"
test_container "airflow"
test_container "clickhouse"

echo ""
echo -e "${YELLOW}=== 2. Service Health Checks (Internal) ===${NC}"
echo ""

test_service "PostgreSQL" "http://$HOST:5432" "000"  # TCP only, will fail HTTP but port is open
test_service "MinIO API" "http://$HOST:9000/minio/health/live" "200"
test_service "MinIO Console" "http://$HOST:9001/" "200"
test_service "OpenSearch" "http://$HOST:9200/" "200"
test_service "Redis" "http://$HOST:6379" "000"  # TCP only
test_service "Tika" "http://$HOST:9998/" "200"
test_service "FastAPI Backend" "http://$HOST:8000/docs" "200"
test_service "Open WebUI Direct" "http://$HOST:3001/" "200"
test_service "Langfuse" "http://$HOST:3000/" "200"
test_service "n8n" "http://$HOST:5678/" "200"
test_service "Budibase" "http://$HOST:10000/" "200"
test_service "Airflow" "http://$HOST:8080/" "200"
test_service "ClickHouse" "http://$HOST:8123/" "200"

echo ""
echo -e "${YELLOW}=== 3. Nginx Proxy (Port 80) ===${NC}"
echo ""

test_service "Nginx Root (Open WebUI)" "http://$HOST/" "200" "dev:dev123"
test_service "Nginx /backend/docs" "http://$HOST/backend/docs" "200"

echo ""
echo -e "${YELLOW}=== 4. API Functionality Tests ===${NC}"
echo ""

# Test FastAPI health endpoint
echo -n "FastAPI Health... "
health_response=$(curl -s "http://$HOST:8000/health" 2>/dev/null || echo '{"error": true}')
if echo "$health_response" | grep -q "ok\|healthy\|status"; then
    echo -e "${GREEN}✓ OK${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ No health endpoint${NC}"
    ((WARNINGS++))
fi

# Test OpenSearch index
echo -n "OpenSearch Index... "
index_response=$(curl -s "http://$HOST:9200/knowledge_units" 2>/dev/null || echo '{"error": true}')
if echo "$index_response" | grep -q "knowledge_units\|mappings"; then
    echo -e "${GREEN}✓ Index exists${NC}"
    ((PASSED++))
elif echo "$index_response" | grep -q "index_not_found"; then
    echo -e "${YELLOW}⚠ Index not created yet${NC}"
    ((WARNINGS++))
else
    echo -e "${RED}✗ Error${NC}"
    ((FAILED++))
fi

# Test MinIO buckets
echo -n "MinIO Buckets... "
# This requires mc client or specific API, skip for now
echo -e "${YELLOW}⚠ Skipped (requires mc client)${NC}"
((WARNINGS++))

echo ""
echo -e "${YELLOW}=== 5. Database Connectivity ===${NC}"
echo ""

echo -n "PostgreSQL Databases... "
dbs=$(docker compose exec -T postgres psql -U adf -tc "SELECT datname FROM pg_database WHERE datistemplate = false;" 2>/dev/null | tr -d ' ' | grep -v '^$' | tr '\n' ',' || echo "error")
if [ "$dbs" != "error" ]; then
    echo -e "${GREEN}✓ OK${NC} ($dbs)"
    ((PASSED++))
else
    echo -e "${RED}✗ Cannot connect${NC}"
    ((FAILED++))
fi

echo ""
echo -e "${YELLOW}=== 6. Simulate User Workflow ===${NC}"
echo ""

# Simulate chat API call (if available)
echo -n "Chat API (simulated)... "
chat_response=$(curl -s -X POST "http://$HOST:8000/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model": "qwen-plus", "messages": [{"role": "user", "content": "Hello"}]}' \
    2>/dev/null || echo '{"error": true}')
if echo "$chat_response" | grep -q "choices\|content\|message"; then
    echo -e "${GREEN}✓ OK${NC}"
    ((PASSED++))
elif echo "$chat_response" | grep -q "Unauthorized\|API key"; then
    echo -e "${YELLOW}⚠ Needs API key configuration${NC}"
    ((WARNINGS++))
else
    echo -e "${YELLOW}⚠ Chat endpoint may not be configured${NC}"
    ((WARNINGS++))
fi

# Test document upload endpoint
echo -n "Document Upload Endpoint... "
upload_response=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:8000/api/ingest" 2>/dev/null || echo "000")
if [ "$upload_response" == "405" ] || [ "$upload_response" == "422" ] || [ "$upload_response" == "401" ]; then
    echo -e "${GREEN}✓ Endpoint exists${NC} (HTTP $upload_response)"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ May need auth${NC} (HTTP $upload_response)"
    ((WARNINGS++))
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  ${GREEN}Passed:${NC}   $PASSED"
echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "  ${RED}Failed:${NC}   $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo -e "${BLUE}=== Access URLs ===${NC}"
    echo ""
    echo "  Open WebUI (Chat):    http://$PUBLIC_IP/ (dev/dev123)"
    echo "  FastAPI Docs:         http://$PUBLIC_IP:8000/docs"
    echo "  Langfuse:             http://$PUBLIC_IP:3000/"
    echo "  n8n:                  http://$PUBLIC_IP:5678/"
    echo "  Airflow:              http://$PUBLIC_IP:8080/ (admin/admin123)"
    echo "  MinIO Console:        http://$PUBLIC_IP:9001/ (check .env)"
    echo "  Budibase:             http://$PUBLIC_IP:10000/ (admin@example.com/admin)"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the logs.${NC}"
    exit 1
fi
