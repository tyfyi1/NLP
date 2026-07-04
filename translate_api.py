from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import tempfile
import shutil

# 添加自动翻译路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '自动翻译'))

from translator_delta import DeltaTranslatorAgent

app = Flask(__name__)
CORS(app)

# 全局翻译器实例
translator = None

def init_translator():
    """初始化翻译器"""
    global translator
    try:
        translator = DeltaTranslatorAgent()
        print("翻译器初始化成功")
    except Exception as e:
        print(f"警告：翻译器初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        translator = None

@app.route('/api/translate', methods=['POST'])
def translate_text_api():
    """
    翻译文本API接口
    
    请求体格式：
    {
        "text": "需要翻译的文本",
        "source_lang": "en",
        "target_lang": "zh",
        "style": "technical"
    }
    
    返回格式：
    {
        "success": true,
        "translation": "翻译结果",
        "message": "成功"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                "success": False,
                "translation": "",
                "message": "缺少必要参数: text"
            }), 400
        
        text = data['text']
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', 'zh')
        style = data.get('style', 'technical')
        
        if not translator:
            return jsonify({
                "success": False,
                "translation": "",
                "message": "翻译器未初始化，请检查配置"
            }), 500
        
        # 执行翻译
        translation = translator.translate_text(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            style=style
        )
        
        if translation:
            return jsonify({
                "success": True,
                "translation": translation,
                "message": "翻译成功"
            })
        else:
            return jsonify({
                "success": False,
                "translation": "",
                "message": "翻译失败，请重试"
            }), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "translation": "",
            "message": f"服务器错误: {str(e)}"
        }), 500

@app.route('/api/translate-file', methods=['POST'])
def translate_file_api():
    """
    翻译文件API接口
    
    支持文件格式：PDF、Markdown、Word、TXT
    
    返回格式：
    {
        "success": true,
        "translation": "翻译结果",
        "message": "成功"
    }
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "translation": "",
                "message": "缺少文件"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "translation": "",
                "message": "未选择文件"
            }), 400
        
        source_lang = request.form.get('source_lang', 'auto')
        target_lang = request.form.get('target_lang', 'zh')
        style = request.form.get('style', 'technical')
        
        if not translator:
            return jsonify({
                "success": False,
                "translation": "",
                "message": "翻译器未初始化，请检查配置"
            }), 500
        
        # 保存临时文件
        temp_dir = tempfile.mkdtemp()
        try:
            file_ext = os.path.splitext(file.filename)[1].lower()
            temp_file_path = os.path.join(temp_dir, file.filename)
            file.save(temp_file_path)
            
            # 使用translator_delta的translate_file方法
            output_path = translator.translate_file(
                input_path=temp_file_path,
                source_lang=source_lang,
                target_lang=target_lang,
                style=style,
                pdf_output_type='md'
            )
            
            # 读取翻译结果
            if output_path and os.path.exists(output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    translation = f.read()
                
                return jsonify({
                    "success": True,
                    "translation": translation,
                    "message": "文件翻译成功"
                })
            else:
                return jsonify({
                    "success": False,
                    "translation": "",
                    "message": "翻译文件生成失败"
                }), 500
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "translation": "",
            "message": f"服务器错误: {str(e)}"
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "translator_initialized": translator is not None
    })

if __name__ == '__main__':
    init_translator()
    print("=" * 70)
    print("          AI 论文翻译 API 服务")
    print("=" * 70)
    print(f"服务启动于: http://localhost:5003")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5003, debug=True)