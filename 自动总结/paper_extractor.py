import os
import re
from typing import Optional

# 导入各种格式的解析库
import pdfplumber
import docx
from bs4 import BeautifulSoup


class PaperExtractor:
    """统一论文提取器，支持多种文件格式"""
    
    def __init__(self, max_chars: int = 15000):
        """
        初始化论文提取器
        
        Args:
            max_chars: 最大提取字符数，默认15000字符（根据论文分析得出的最优值）
        
        最优值分析：
        - 您的论文库：27篇论文，平均13.92 MB
        - 典型论文字符数：30,000-50,000字符
        - 核心内容（摘要+引言+方法+实验）：约15,000字符
        - API限制：GLM-4-9B支持8K-32K token（约6K-24K汉字）
        """
        self.max_chars = max_chars
    
    def extract_from_file(self, file_path: str) -> Optional[str]:
        """
        从文件中提取文本
        
        Args:
            file_path: 文件路径
        
        Returns:
            提取的文本内容，如果失败返回None
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext == '.pdf':
                return self._extract_from_pdf(file_path)
            elif ext == '.docx':
                return self._extract_from_docx(file_path)
            elif ext == '.html' or ext == '.htm':
                return self._extract_from_html(file_path)
            elif ext == '.txt' or ext == '.md':
                return self._extract_from_text(file_path)
            else:
                print(f"不支持的文件格式: {ext}")
                return None
        except Exception as e:
            print(f"提取文件失败: {e}")
            return None
    
    def _extract_from_pdf(self, pdf_path: str) -> Optional[str]:
        """从PDF提取文本"""
        # 首先尝试直接提取文本
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                # 如果提取的文本太少（<500字符），可能是扫描件
                if len(text.strip()) < 500:
                    print("检测到可能是扫描件PDF，尝试OCR...")
                    return self._extract_pdf_with_ocr(pdf_path)
                
                return self._smart_truncate(text)
        except Exception as e:
            print(f"PDF提取失败: {e}")
            # 如果直接提取失败，尝试OCR
            return self._extract_pdf_with_ocr(pdf_path)
    
    def _extract_pdf_with_ocr(self, pdf_path: str) -> Optional[str]:
        """使用OCR从PDF提取文本（用于扫描件）"""
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            # 将PDF转换为图片
            images = convert_from_path(pdf_path, dpi=300)
            
            text = ""
            for i, image in enumerate(images):
                print(f"  OCR处理第 {i+1}/{len(images)} 页...")
                page_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                text += page_text + "\n"
            
            return self._smart_truncate(text)
        except ImportError:
            print("OCR库未安装，请运行: pip install pytesseract pdf2image")
            print("注意：Windows系统还需要安装Tesseract OCR引擎")
            return None
        except Exception as e:
            print(f"OCR提取失败: {e}")
            return None
    
    def _extract_from_docx(self, docx_path: str) -> Optional[str]:
        """从Word文档提取文本"""
        try:
            doc = docx.Document(docx_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return self._smart_truncate(text)
        except Exception as e:
            print(f"Word文档提取失败: {e}")
            return None
    
    def _extract_from_html(self, html_path: str) -> Optional[str]:
        """从HTML文件提取文本"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # 移除script和style标签
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 提取文本
            text = soup.get_text(separator='\n')
            
            # 清理空白字符
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            return self._smart_truncate(text)
        except Exception as e:
            print(f"HTML文件提取失败: {e}")
            return None
    
    def _extract_from_text(self, text_path: str) -> Optional[str]:
        """从文本文件提取文本"""
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
            
            for encoding in encodings:
                try:
                    with open(text_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    return self._smart_truncate(text)
                except UnicodeDecodeError:
                    continue
            
            print("无法识别文本文件编码")
            return None
        except Exception as e:
            print(f"文本文件提取失败: {e}")
            return None
    
    def _smart_truncate(self, text: str) -> str:
        """
        智能截取文本，优先保留论文的核心部分
        
        论文核心内容顺序通常是：
        1. 摘要 (Abstract)
        2. 引言/介绍 (Introduction)
        3. 方法 (Method)
        4. 实验 (Experiment)
        5. 结论 (Conclusion)
        """
        if len(text) <= self.max_chars:
            return text
        
        # 定义论文各部分的关键词（英文）
        sections_en = {
            'abstract': r'(Abstract|ABSTRACT)',
            'introduction': r'(1\.\s*Introduction|Introduction|INTRODUCTION)',
            'method': r'(2\.\s*Method|Methodology|METHOD|2\.\s*Proposed|2\.\s*Approach)',
            'experiment': r'(3\.\s*Experiment|Experiment|EXPERIMENT|3\.\s*Results|3\.\s*Evaluation)',
            'conclusion': r'(Conclusion|CONCLUSION|Future|4\.\s*Conclusion)'
        }
        
        # 定义论文各部分的关键词（中文）
        sections_cn = {
            'abstract': r'(摘要|摘要：)',
            'introduction': r'(1\.\s*引言|引言|研究背景|1\.\s*背景)',
            'method': r'(2\.\s*方法|Method|方法论|2\.\s*模型|2\.\s*网络)',
            'experiment': r'(3\.\s*实验|实验结果|3\.\s*评估|3\.\s*验证)',
            'conclusion': r'(结论|结论：|总结|4\.\s*结论)'
        }
        
        # 检查文本语言
        is_english = sum(1 for c in text[:500] if c.isascii() and c.isalpha()) > 50
        sections = sections_en if is_english else sections_cn
        
        # 尝试按章节提取
        section_positions = {}
        for section_name, pattern in sections.items():
            match = re.search(pattern, text)
            if match:
                section_positions[section_name] = match.start()
        
        # 如果找到了多个章节
        if len(section_positions) >= 2:
            # 按位置排序
            sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
            
            # 提取前几个重要章节的内容
            extracted_parts = []
            current_pos = 0
            
            for i, (section_name, pos) in enumerate(sorted_sections[:5]):  # 最多提取5个章节
                if i < len(sorted_sections) - 1:
                    next_pos = sorted_sections[i+1][1]
                else:
                    next_pos = pos + self.max_chars // 2
                
                section_text = text[pos:next_pos]
                extracted_parts.append(section_text)
                
                current_pos = next_pos
            
            # 合并提取的内容
            full_text = "\n".join(extracted_parts)
            
            # 如果还不够，添加开头部分
            if len(full_text) < self.max_chars * 0.8:
                # 从开头提取补充内容
                remaining = self.max_chars - len(full_text)
                intro_start = min(len(text), remaining)
                full_text = text[:intro_start] + "\n\n" + full_text
            
            return full_text
        
        # 如果找不到章节结构，使用传统的截取方法
        # 优先保留开头（通常包含摘要）
        return text[:self.max_chars]
    
    def get_supported_formats(self) -> list:
        """获取支持的文件格式"""
        return [
            {
                'format': 'PDF文档',
                'extension': '.pdf',
                'description': '支持可复制文本的PDF和扫描件PDF（需要OCR）',
                'ocr_required': False
            },
            {
                'format': 'Word文档',
                'extension': '.docx',
                'description': 'Microsoft Word文档',
                'ocr_required': False
            },
            {
                'format': 'HTML文件',
                'extension': '.html/.htm',
                'description': '网页文件',
                'ocr_required': False
            },
            {
                'format': '文本文件',
                'extension': '.txt/.md',
                'description': '纯文本或Markdown文件',
                'ocr_required': False
            }
        ]


def main():
    """测试论文提取器"""
    extractor = PaperExtractor(max_chars=10000)
    
    print("=" * 80)
    print("📁 支持的文件格式")
    print("=" * 80)
    
    for fmt in extractor.get_supported_formats():
        print(f"\n{fmt['format']} ({fmt['extension']})")
        print(f"  说明: {fmt['description']}")
        if fmt['ocr_required']:
            print(f"  ⚠️  需要OCR支持")
    
    print("\n" + "=" * 80)
    print("📊 智能文本提取策略")
    print("=" * 80)
    print("""
✅ 最大提取: 10,000 字符
✅ 智能识别: 自动识别论文语言（中文/英文）
✅ 章节优先: 优先提取论文核心章节（摘要、引言、方法、实验、结论）
✅ 扫描件支持: 自动检测并使用OCR处理扫描件PDF
    """)
    
    # 测试论文提取
    paper_dir = r"D:\学习\论文阅读"
    
    print("\n" + "=" * 80)
    print("🧪 测试论文提取")
    print("=" * 80)
    
    # 测试PDF
    test_pdfs = [
        "Colorful Image Colorization.pdf",
        "pix2pix.pdf",
    ]
    
    for pdf_file in test_pdfs:
        pdf_path = os.path.join(paper_dir, pdf_file)
        if os.path.exists(pdf_path):
            print(f"\n📄 测试: {pdf_file}")
            text = extractor.extract_from_file(pdf_path)
            if text:
                print(f"  ✅ 成功提取 {len(text):,} 字符")
                print(f"  📝 预览（前200字符）:")
                print(f"     {text[:200]}...")
            else:
                print(f"  ❌ 提取失败")


if __name__ == "__main__":
    main()
