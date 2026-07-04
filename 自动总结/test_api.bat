@echo off
chcp 65001 > nul
echo ================================================
echo          论文总结API - 诊断测试
echo ================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python
    pause
    exit /b 1
)

echo [1/5] 检查依赖库...
python -c "import requests" 2>nul
if %errorlevel% neq 0 (
    echo [错误] requests库未安装
    echo 正在安装...
    pip install requests
)
echo [OK] 依赖库检查完成

echo.
echo [2/5] 检查API服务状态...
python -c "import requests; r = requests.get('http://localhost:5001/api/health', timeout=5); print(r.json())" 2>nul
if %errorlevel% neq 0 (
    echo [错误] 无法连接到API服务
    echo 请确保API服务正在运行: python api.py
    echo.
    echo 启动API服务中...
    start cmd /k "cd /d d:\pycode\自然语言处理\software\自动总结 && python api.py"
    timeout /t 5
)

echo.
echo [3/5] 测试API调用...
python -c "
import requests
import json

url = 'http://localhost:5001/api/summary'
data = {
    'text': '这是一段测试文本，用于验证API是否正常工作。',
    'type': 'simple',
    'max_tokens': 100
}

try:
    response = requests.post(url, json=data, timeout=30)
    result = response.json()
    print('API返回:', json.dumps(result, ensure_ascii=False, indent=2))

    if result.get('success'):
        print('[成功] API调用正常！')
    else:
        print('[失败]', result.get('message', '未知错误'))
except Exception as e:
    print('[错误]', str(e))
"

echo.
echo [4/5] 检查API密钥配置...
python -c "
import os
api_key = os.getenv('SILICONFLOW_API_KEY')
if api_key:
    print('[OK] API密钥已设置:', api_key[:10] + '...')
else:
    print('[警告] API密钥未设置')
"

echo.
echo [5/5] 直接测试模型API...
python -c "
import requests
import os

api_key = os.getenv('SILICONFLOW_API_KEY') or 'sk-ogopmfbtujtsmopibvfmaigawixcmyvuwyoaoasnsyrsdpft'
url = 'https://api.siliconflow.cn/v1/chat/completions'

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}

data = {
    'model': 'THUDM/GLM-4-9B-0414',
    'messages': [
        {
            'role': 'user',
            'content': '你好，这是一个测试消息。请回复OK。'
        }
    ],
    'max_tokens': 50
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    result = response.json()

    if 'choices' in result:
        print('[OK] 模型API调用成功！')
        print('回复:', result['choices'][0]['message']['content'])
    else:
        print('[错误] 模型API返回异常')
        print(result)
except Exception as e:
    print('[错误]', str(e))
"

echo.
echo ================================================
echo          诊断完成
echo ================================================
pause