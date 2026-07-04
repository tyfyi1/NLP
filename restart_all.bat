@echo off
chcp 65001 > nul
echo ================================================
echo          AI文献辅助系统 - 一键重启脚本
echo ================================================
echo.

echo [1/5] 正在停止所有服务...
taskkill /F /IM node.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 1 /nobreak >nul
echo       已停止所有服务

echo.
echo [2/5] 启动论文检索API服务 (端口5002)...
start "论文检索API" cmd /k "cd /d d:\pycode\自然语言处理\software\自动检索\paper_retriever && python api_service.py"

echo.
echo [3/5] 启动论文总结API服务 (端口5001)...
start "论文总结API" cmd /k "cd /d d:\pycode\自然语言处理\software\自动总结 && python api.py"

echo.
echo [4/5] 启动论文翻译API服务 (端口5003)...
start "论文翻译API" cmd /k "cd /d d:\pycode\自然语言处理\software && python translate_api.py"

echo.
echo [5/5] 启动综述生成API服务 (端口8002)...
start "综述生成API" cmd /k "cd /d d:\pycode\自然语言处理\software\综述生成 && python main.py"

echo.
echo [6/5] 启动主服务器 (端口3002)...
start "主服务器" cmd /k "cd /d d:\pycode\自然语言处理\software && node server.js"

echo.
echo ================================================
echo 服务启动完成，请等待所有窗口加载
echo ================================================
echo.
echo 访问地址: http://localhost:3002
echo.
echo 请检查每个服务窗口是否有错误信息
echo 如果某个服务启动失败，请单独手动启动
echo ================================================
pause