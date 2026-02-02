#!/bin/bash
# FFmpeg Microservice 部署测试脚本
# 用法: ./test.sh [HOST]
# 示例: ./test.sh localhost:8000
#       ./test.sh ffmpeg-api:8000  (从 n8n 容器内测试)

HOST=${1:-"68.233.127.145:8123"}
API_KEY=${2:-"your_secret_key_here"}
BASE_URL="http://$HOST"
AUTH_HEADER="X-API-Key: $API_KEY"

echo "=========================================="
echo "FFmpeg Microservice 部署测试"
echo "目标地址: $BASE_URL"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; }

# 测试 1: 健康检查
echo ""
echo "1. 测试健康检查 (GET /health)"
RESPONSE=$(curl -s "$BASE_URL/health")
if echo "$RESPONSE" | grep -q "ok"; then
    pass "健康检查通过"
    echo "   响应: $RESPONSE"
else
    fail "健康检查失败"
    echo "   响应: $RESPONSE"
    exit 1
fi

# 测试 2: 文件列表
echo ""
echo "2. 测试文件列表 (GET /files)"
RESPONSE=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/files")
if echo "$RESPONSE" | grep -q "files"; then
    pass "文件列表接口正常"
    echo "   响应: $RESPONSE"
else
    fail "文件列表接口失败"
    echo "   响应: $RESPONSE"
fi

# 测试 3: 合并接口（参数校验）
echo ""
echo "3. 测试参数校验 (POST /merge - 少于2个URL)"
RESPONSE=$(curl -s -X POST "$BASE_URL/merge" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"urls": ["https://example.com/1.mp4"]}')
if echo "$RESPONSE" | grep -q "At least 2 URLs"; then
    pass "参数校验正常"
else
    fail "参数校验异常"
    echo "   响应: $RESPONSE"
fi

# 测试 4: 实际视频合并（可选）
echo ""
echo "4. 测试视频合并 (可选 - 需要有效视频URL)"
echo "   跳过 - 需要提供真实视频 URL 进行测试"
echo "   手动测试命令:"
echo "   curl -X POST $BASE_URL/merge \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H '$AUTH_HEADER' \\"
echo "     -d '{\"urls\": [\"VIDEO_URL_1\", \"VIDEO_URL_2\"], \"save_to_disk\": true}'"

echo ""
echo "=========================================="
echo "基础测试完成！"
echo "=========================================="
