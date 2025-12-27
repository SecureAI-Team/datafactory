"""
视觉理解服务
调用 Qwen-VL API 进行图片理解、表格识别、图表分析
"""
import os
import base64
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

import httpx

logger = logging.getLogger(__name__)


class VisionTaskType(str, Enum):
    """视觉任务类型"""
    GENERAL_QA = "general_qa"          # 通用图片问答
    TABLE_EXTRACT = "table_extract"     # 表格提取
    CHART_ANALYZE = "chart_analyze"     # 图表分析
    OCR = "ocr"                         # 文字识别
    DOCUMENT_PARSE = "document_parse"   # 文档解析


@dataclass
class VisionResult:
    """视觉分析结果"""
    success: bool
    task_type: VisionTaskType
    text_content: str = ""              # 文字内容
    structured_data: Dict = field(default_factory=dict)  # 结构化数据
    tables: List[Dict] = field(default_factory=list)     # 提取的表格
    charts: List[Dict] = field(default_factory=list)     # 图表数据
    confidence: float = 0.0
    raw_response: str = ""
    error: str = ""


class VisionService:
    """视觉理解服务"""
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = base_url or os.getenv(
            "QWEN_VL_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model or os.getenv("QWEN_VL_MODEL", "qwen-vl-max")
        
        self._client = None
    
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "DASHSCOPE_API_KEY 未配置。请在环境变量中设置 DASHSCOPE_API_KEY"
                )
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client
    
    def analyze_image(
        self,
        image_data: Union[bytes, str],
        question: str = None,
        task_type: VisionTaskType = VisionTaskType.GENERAL_QA,
    ) -> VisionResult:
        """
        分析图片
        
        Args:
            image_data: 图片数据（bytes）或图片URL
            question: 用户问题
            task_type: 任务类型
        
        Returns:
            VisionResult
        """
        try:
            # 构建图片内容
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode("utf-8")
                image_url = f"data:image/png;base64,{image_base64}"
            else:
                image_url = image_data
            
            # 根据任务类型构建 prompt
            prompt = self._build_prompt(question, task_type)
            
            # 构建请求
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            
            # 调用 API
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 4096,
                },
            )
            response.raise_for_status()
            
            result_data = response.json()
            content = result_data["choices"][0]["message"]["content"]
            
            # 解析结果
            return self._parse_response(content, task_type)
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return VisionResult(
                success=False,
                task_type=task_type,
                error=str(e),
            )
    
    def _build_prompt(self, question: str, task_type: VisionTaskType) -> str:
        """构建不同任务的 Prompt"""
        
        if task_type == VisionTaskType.TABLE_EXTRACT:
            return """请分析这张图片中的表格内容。

要求：
1. 识别所有表格
2. 提取表头和数据行
3. 以JSON格式返回，格式如下：
```json
{
  "tables": [
    {
      "title": "表格标题（如有）",
      "headers": ["列1", "列2", ...],
      "rows": [
        ["数据1", "数据2", ...],
        ...
      ]
    }
  ],
  "summary": "表格内容摘要"
}
```

如果没有表格，返回 {"tables": [], "summary": "图片中没有表格"}
"""
        
        elif task_type == VisionTaskType.CHART_ANALYZE:
            return """请分析这张图片中的图表。

要求：
1. 识别图表类型（柱状图、折线图、饼图等）
2. 提取图表数据
3. 以JSON格式返回，格式如下：
```json
{
  "charts": [
    {
      "type": "图表类型",
      "title": "图表标题",
      "x_axis": "X轴标签",
      "y_axis": "Y轴标签",
      "data": [
        {"label": "类别1", "value": 100},
        ...
      ]
    }
  ],
  "insights": "图表展示的主要趋势或结论"
}
```
"""
        
        elif task_type == VisionTaskType.OCR:
            return """请识别这张图片中的所有文字内容。

要求：
1. 按阅读顺序输出文字
2. 保持原有的段落结构
3. 标注特殊格式（如标题、列表等）

直接输出识别到的文字内容。
"""
        
        elif task_type == VisionTaskType.DOCUMENT_PARSE:
            return """请解析这张文档图片的结构和内容。

要求：
1. 识别文档结构（标题、段落、列表、表格等）
2. 提取所有文字内容
3. 以JSON格式返回，格式如下：
```json
{
  "title": "文档标题",
  "sections": [
    {
      "heading": "章节标题",
      "content": "章节内容",
      "type": "paragraph/list/table"
    }
  ],
  "metadata": {
    "page_number": 1,
    "has_images": false
  }
}
```
"""
        
        else:  # GENERAL_QA
            if question:
                return f"""请根据图片内容回答以下问题：

{question}

要求：
1. 仔细观察图片中的所有内容
2. 给出准确、详细的回答
3. 如果图片中没有相关信息，请明确说明
"""
            else:
                return """请描述这张图片的内容。

要求：
1. 详细描述图片中的主要元素
2. 说明图片的用途或含义
3. 如果有文字或数据，请一并说明
"""
    
    def _parse_response(self, content: str, task_type: VisionTaskType) -> VisionResult:
        """解析 LLM 响应"""
        
        result = VisionResult(
            success=True,
            task_type=task_type,
            raw_response=content,
            confidence=0.9,
        )
        
        # 尝试提取 JSON
        try:
            # 查找 JSON 块
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
                result.structured_data = data
                
                if "tables" in data:
                    result.tables = data["tables"]
                if "charts" in data:
                    result.charts = data["charts"]
                if "summary" in data:
                    result.text_content = data["summary"]
                elif "insights" in data:
                    result.text_content = data["insights"]
            else:
                result.text_content = content
                
        except json.JSONDecodeError:
            result.text_content = content
        
        return result
    
    def extract_tables(self, image_data: Union[bytes, str]) -> VisionResult:
        """便捷方法：提取表格"""
        return self.analyze_image(image_data, task_type=VisionTaskType.TABLE_EXTRACT)
    
    def analyze_chart(self, image_data: Union[bytes, str]) -> VisionResult:
        """便捷方法：分析图表"""
        return self.analyze_image(image_data, task_type=VisionTaskType.CHART_ANALYZE)
    
    def ocr(self, image_data: Union[bytes, str]) -> VisionResult:
        """便捷方法：OCR 文字识别"""
        return self.analyze_image(image_data, task_type=VisionTaskType.OCR)
    
    def parse_document(self, image_data: Union[bytes, str]) -> VisionResult:
        """便捷方法：解析文档"""
        return self.analyze_image(image_data, task_type=VisionTaskType.DOCUMENT_PARSE)
    
    def ask_about_image(self, image_data: Union[bytes, str], question: str) -> VisionResult:
        """便捷方法：图片问答"""
        return self.analyze_image(image_data, question, VisionTaskType.GENERAL_QA)
    
    def close(self):
        """关闭客户端"""
        if self._client:
            self._client.close()
            self._client = None


# ==================== 模块级便捷函数 ====================

_default_service: Optional[VisionService] = None


def get_vision_service() -> VisionService:
    """获取视觉服务实例"""
    global _default_service
    if _default_service is None:
        _default_service = VisionService()
    return _default_service


def analyze_image(
    image_data: Union[bytes, str],
    question: str = None,
    task_type: VisionTaskType = VisionTaskType.GENERAL_QA,
) -> VisionResult:
    """便捷函数：分析图片"""
    return get_vision_service().analyze_image(image_data, question, task_type)


def extract_tables(image_data: Union[bytes, str]) -> VisionResult:
    """便捷函数：提取表格"""
    return get_vision_service().extract_tables(image_data)


def ocr_image(image_data: Union[bytes, str]) -> VisionResult:
    """便捷函数：OCR"""
    return get_vision_service().ocr(image_data)

