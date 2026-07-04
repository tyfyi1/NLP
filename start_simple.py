import subprocess
import threading
import time
import os
import sys

def start_summary_api():
    """启动论文总结API"""
    print("启动论文总结API服务...")
    os.chdir("D:\\pycode\\自然语言处理\\software\\自动总结")
    subprocess.run(["python", "api.py"])

def start_http_server():
    """启动简单HTTP服务器托管前端"""
    print("启动前端HTTP服务器...")
    os.chdir("D:\\pycode\\自然语言处理\\software")
    subprocess.run(["python", "-m", "http.server", "8080"])

if __name__ == "__main__":
    print("========================================")
    print("AI文献辅助系统 - 简易启动")
    print("========================================")
    print()
    
    # 启动论文总结API
    api_process = subprocess.Popen(
        ["python", "api.py"],
        cwd="D:\\pycode\\自然语言处理\\software\\自动总结",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # 等待API启动
    time.sleep(4)
    
    # 启动HTTP服务器
    print("启动前端HTTP服务器...")
    print("========================================")
    print("访问地址: http://localhost:8080")
    print("论文总结API: http://localhost:5001")
    print("========================================")
    print()
    
    os.chdir("D:\\pycode\\自然语言处理\\software")
    subprocess.run(["python", "-m", "http.server", "8080"])