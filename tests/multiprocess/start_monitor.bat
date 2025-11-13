@echo off
chcp 65001 >nul
echo ========================================
echo   CapsWriter 资源监控工具
echo ========================================
echo.

cd /d "%~dp0\..\..\"

echo [信息] 项目目录: %CD%
echo [信息] 按 Ctrl+C 停止监控
echo.

python tests\multiprocess\monitor_resources.py --interval 1.0

pause
