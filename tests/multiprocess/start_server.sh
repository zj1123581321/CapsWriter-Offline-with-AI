#!/bin/bash

echo "========================================"
echo "  CapsWriter 多进程测试 Server"
echo "========================================"
echo

# 获取脚本所在目录的父目录的父目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "[信息] 项目目录: $PWD"
echo

python tests/multiprocess/test_core_multiprocess.py
