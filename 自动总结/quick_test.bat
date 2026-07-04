@echo off
chcp 65001 > nul
echo ================================================
echo       直接测试论文总结API
echo ================================================
echo.

cd /d d:\pycode\自然语言处理\software\自动总结

echo [1] 正在启动API服务...
start "论文总结API测试" cmd /k "python api.py"
echo     等待服务启动...
timeout /t 3

echo.
echo [2] 等待服务完全启动...
timeout /t 2

echo.
echo [3] 测试API健康检查...
python -c "import requests; r = requests.get('http://localhost:5001/api/health', timeout=5); print(r.json())"

echo.
echo [4] 测试生成总结...
python -c "
import requests
import json

url = 'http://localhost:5001/api/summary'
data = {
    'text': '深度学习是机器学习的一个分支，使用多层神经网络来学习数据的分层表示。在计算机视觉领域，卷积神经网络(CNN)已经取得了突破性进展。Transformer架构自2017年提出以来，已成为自然语言处理的主流模型。',
    'type': 'simple',
    'max_tokens': 200
}

try:
    print('发送请求到:', url)
    response = requests.post(url, json=data, timeout=60)
    result = response.json()
    print('状态码:', response.status_code)
    print('返回结果:', json.dumps(result, ensure_ascii=False, indent=2))

    if result.get('success'):
        print()
        print('[成功] API正常工作！')
        print('生成的总结:', result.get('summary', '')[:200], '...')
    else:
        print()
        print('[失败]', result.get('message', '未知错误'))
except Exception as e:
    print()
    print('[错误]', str(e))
"

echo.
echo ================================================
echo 测试完成
echo ================================================
pause