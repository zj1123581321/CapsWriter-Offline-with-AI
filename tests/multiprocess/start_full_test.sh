#!/bin/bash

echo "========================================"
echo "  CapsWriter 一键测试脚本"
echo "========================================"
echo

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "[信息] 项目目录: $PWD"
echo "[提示] 请准备 3 个终端窗口"
echo

python tests/multiprocess/run_test.py
