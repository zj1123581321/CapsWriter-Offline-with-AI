@echo off
chcp 65001 >nul
echo ========================================
echo   CapsWriter 多进程测试 Server
echo ========================================
echo.

cd /d "%~dp0\..\..\"

echo [信息] 项目目录: %CD%
echo.

python tests\multiprocess\test_core_multiprocess.py

pause
