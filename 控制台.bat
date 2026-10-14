@echo off
title 项目控制台
cd /d %~dp0

echo ============================================
echo    正在启动项目控制台...
echo    马上会弹出浏览器, 没弹就手动打开:
echo    http://127.0.0.1:5001/
echo ============================================
echo.

python launcher.py

echo.
echo 控制台已关闭
pause
