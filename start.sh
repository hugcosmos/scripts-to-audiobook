#!/bin/bash
# 一键启动前后端服务

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 端口配置
BACKEND_PORT=8000
FRONTEND_PORT=5000

# 检查端口是否被占用
check_port() {
    lsof -i:$1 >/dev/null 2>&1
}

# 查找可用端口
find_available_port() {
    local port=$1
    while check_port $port; do
        port=$((port + 1))
    done
    echo $port
}

# 停止占用指定端口的进程
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}  释放端口 $port (PID: $pid)${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 0.5
    fi
}

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务...${NC}"
    # 停止后端
    lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    # 停止前端
    pkill -f "tsx server/index.ts" 2>/dev/null || true
    exit 0
}

# 设置清理钩子
trap cleanup INT TERM EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Scripts to Audiobook - 启动服务     ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 启动前清理端口
echo -e "${YELLOW}清理端口占用...${NC}"
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# 检查依赖
check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${YELLOW}警告: $1 未安装${NC}"
        return 1
    fi
    return 0
}

# 检查 Python 依赖（静默检查，只有需要安装时才输出）
check_python_deps() {
    if ! python3 -c "import edge_tts, fastapi, uvicorn, pydub, aiosqlite, websocket, hmac, hashlib, base64, tempfile" 2>/dev/null; then
        echo -e "${YELLOW}正在安装 Python 依赖...${NC}"
        pip3 install edge-tts fastapi uvicorn pydub aiosqlite websocket-client -q 2>&1 | grep -v "already satisfied" || true
        echo -e "${GREEN}✓ Python 依赖安装完成${NC}"
    fi
}

# 检查 Node 依赖
check_node_deps() {
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}正在安装前端依赖...${NC}"
        cd frontend && npm install && cd ..
    fi
}

check_dependency python3 || exit 1
check_dependency pip3 || exit 1
check_dependency node || exit 1
check_dependency npm || exit 1

# 安装依赖
check_python_deps
check_node_deps

# 确保日志目录存在
mkdir -p logs

# 检测可用端口（macOS 可能会占用 5000 端口）
FRONTEND_PORT=$(find_available_port $FRONTEND_PORT)

if [ "$FRONTEND_PORT" != "5000" ]; then
    echo -e "${YELLOW}⚠ 端口 5000 被占用，自动切换到端口 $FRONTEND_PORT${NC}"
fi

echo ""
echo -e "${GREEN}✓ 依赖检查完成${NC}"
echo ""
echo -e "${BLUE}启动服务:${NC}"
echo -e "  - 后端 API: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo -e "  - 前端应用: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
echo -e "  - 日志文件: ${GREEN}./logs/app.log${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 启动前端
cd "$SCRIPT_DIR/frontend" && PORT=$FRONTEND_PORT npm run dev &
FRONTEND_PID=$!

# 启动后端
cd "$SCRIPT_DIR" && python3 backend/main.py &
BACKEND_PID=$!

# 等待进程
wait $FRONTEND_PID $BACKEND_PID
