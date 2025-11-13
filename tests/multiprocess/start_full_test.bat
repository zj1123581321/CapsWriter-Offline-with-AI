@echo off
chcp 65001 >nul
echo ========================================
echo   CapsWriter 一键测试脚本
echo ========================================
echo.

cd /d "%~dp0\..\..\"

echo [信息] 项目目录: %CD%
echo [提示] 请准备 3 个终端窗口
echo.

python tests\multiprocess\run_test.py

pause
