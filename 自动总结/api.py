from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys

# 添加上级目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from summary_generator import SummaryGenerator

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 启用CORS支持，允许所有来源
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# 全局摘要生成器实例
generator = None

def init_generator():
    """初始化摘要生成器"""
    global generator
    # 优先从环境变量获取API密钥，如果没有则使用备用密钥
    api_key = os.getenv("SILICONFLOW_API_KEY") or "sk-ogopmfbtujtsmopibvfmaigawixcmyvuwyoaoasnsyrsdpft"
    if api_key:
        try:
            generator = SummaryGenerator(api_key=api_key)
            print("摘要生成器初始化成功")
        except Exception as e:
            print(f"摘要生成器初始化失败: {str(e)}")
    else:
        print("警告：未设置SILICONFLOW_API_KEY环境变量")

@app.route('/api/summary', methods=['POST'])
def generate_summary_api():
    """
    生成论文摘要的API接口
    
    请求体格式：
    {
        "text": "论文内容...",
        "type": "simple" 或 "detailed",
        "max_tokens": 500
    }
    
    返回格式：
    {
        "success": true,
        "summary": "生成的摘要内容",
        "message": "成功"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                "success": False,
                "summary": "",
                "message": "缺少必要参数: text"
            }), 400
        
        text = data['text']
        summary_type = data.get('type', 'simple')
        max_tokens = data.get('max_tokens', 500)
        
        if not text.strip():
            return jsonify({
                "success": False,
                "summary": "",
                "message": "输入文本不能为空"
            }), 400
        
        max_input_length = 15000  # 限制最大输入长度
        if len(text) > max_input_length:
            print(f"警告：输入文本过长({len(text)}字符)，已截断至{max_input_length}字符")
            text = text[:max_input_length]
        
        if not generator:
            return jsonify({
                "success": False,
                "summary": "",
                "message": "摘要生成器未初始化，请设置API密钥"
            }), 500
        
        if summary_type == 'detailed':
            summary = generator.generate_detailed_summary(text)
        else:
            summary = generator.generate_summary(text, max_tokens=max_tokens)
        
        if summary:
            return jsonify({
                "success": True,
                "summary": summary,
                "message": "成功"
            })
        else:
            return jsonify({
                "success": False,
                "summary": "",
                "message": "生成摘要失败，请重试"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "summary": "",
            "message": f"服务器错误: {str(e)}"
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "generator_initialized": generator is not None
    })

if __name__ == '__main__':
    init_generator()
    app.run(host='0.0.0.0', port=5001, debug=True)