#!/bin/bash

echo "========================================"
echo "  CapsWriter 并发测试客户端"
echo "========================================"
echo

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "[信息] 项目目录: $PWD"
echo "[信息] 确保 Server 已启动"
echo

python tests/multiprocess/test_concurrent_client.py
