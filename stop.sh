#!/bin/bash
# 停止 Scripts to Audiobook 所有服务

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 端口配置（与 start.sh 保持一致）
BACKEND_PORT=8000
FRONTEND_PORT=5000

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Scripts to Audiobook - 停止服务     ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}正在停止服务...${NC}"

# 停止后端
PID_BACKEND=$(lsof -ti:$BACKEND_PORT 2>/dev/null)
if [ -n "$PID_BACKEND" ]; then
    echo -e "  ${YELLOW}停止后端服务 (端口 $BACKEND_PORT, PID: $PID_BACKEND)${NC}"
    kill -9 $PID_BACKEND 2>/dev/null
fi

# 停止前端 - 检查常用端口范围
STOPPED_FRONTEND=false
for PORT in $(seq 5000 5020); do
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        echo -e "  ${YELLOW}停止前端服务 (端口 $PORT, PID: $PID)${NC}"
        kill -9 $PID 2>/dev/null
        STOPPED_FRONTEND=true
    fi
done

# 停止所有相关的 node 和 python 进程
echo -e "  ${YELLOW}清理残留进程...${NC}"
pkill -f "tsx server/index.ts" 2>/dev/null
pkill -f "python3 backend/main.py" 2>/dev/null
pkill -f "python backend/main.py" 2>/dev/null

echo ""
echo -e "${GREEN}✓ 所有服务已停止${NC}"

# 验证
echo ""
echo -e "${BLUE}端口状态:${NC}"
sleep 0.5

BACKEND_STATUS=$(lsof -ti:$BACKEND_PORT 2>/dev/null && echo -e "${RED}占用${NC}" || echo -e "${GREEN}空闲${NC}")
FRONTEND_STATUS=$(lsof -ti:$FRONTEND_PORT 2>/dev/null && echo -e "${RED}占用${NC}" || echo -e "${GREEN}空闲${NC}")

echo -e "  $BACKEND_PORT (后端): $BACKEND_STATUS"
echo -e "  $FRONTEND_PORT (前端): $FRONTEND_STATUS"

# 如果有残留进程，强制清理
if lsof -ti:$BACKEND_PORT >/dev/null 2>&1 || lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
    echo ""
    echo -e "${YELLOW}⚠ 仍有进程占用端口，强制停止中...${NC}"
    lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 0.5
    echo -e "${GREEN}✓ 强制清理完成${NC}"
fi

echo ""
