#!/bin/bash

echo "========================================"
echo "  CapsWriter 资源监控工具"
echo "========================================"
echo

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "[信息] 项目目录: $PWD"
echo "[信息] 按 Ctrl+C 停止监控"
echo

python tests/multiprocess/monitor_resources.py --interval 1.0
