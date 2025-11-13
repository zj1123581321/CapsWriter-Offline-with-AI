@echo off
chcp 65001 >nul
echo ========================================
echo   CapsWriter 并发测试客户端
echo ========================================
echo.

cd /d "%~dp0\..\..\"

echo [信息] 项目目录: %CD%
echo [信息] 确保 Server 已启动
echo.

python tests\multiprocess\test_concurrent_client.py

pause
