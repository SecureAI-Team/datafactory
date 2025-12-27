"""
表格和图表提取服务
从图片/PDF中提取结构化表格和图表数据
"""
import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

logger = logging.getLogger(__name__)


class TableFormat(str, Enum):
    """表格输出格式"""
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"
    HTML = "html"


@dataclass
class TableCell:
    """表格单元格"""
    value: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False


@dataclass
class ExtractedTable:
    """提取的表格"""
    title: str = ""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    cells: List[TableCell] = field(default_factory=list)
    source_page: int = 0
    confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "row_count": len(self.rows),
            "col_count": len(self.headers) if self.headers else (len(self.rows[0]) if self.rows else 0),
        }
    
    def to_markdown(self) -> str:
        """转换为 Markdown 表格"""
        lines = []
        
        if self.title:
            lines.append(f"**{self.title}**\n")
        
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        
        for row in self.rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(lines)
    
    def to_csv(self) -> str:
        """转换为 CSV"""
        lines = []
        
        if self.headers:
            lines.append(",".join(f'"{h}"' for h in self.headers))
        
        for row in self.rows:
            lines.append(",".join(f'"{cell}"' for cell in row))
        
        return "\n".join(lines)
    
    def get_column(self, col_name: str) -> List[str]:
        """获取指定列的数据"""
        if col_name in self.headers:
            idx = self.headers.index(col_name)
            return [row[idx] for row in self.rows if len(row) > idx]
        return []
    
    def search(self, keyword: str) -> List[Tuple[int, int, str]]:
        """搜索表格内容"""
        results = []
        for i, row in enumerate(self.rows):
            for j, cell in enumerate(row):
                if keyword.lower() in str(cell).lower():
                    results.append((i, j, cell))
        return results


@dataclass
class ChartData:
    """图表数据"""
    chart_type: str = ""  # bar, line, pie, scatter, etc.
    title: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    data_series: List[Dict] = field(default_factory=list)
    legend: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.chart_type,
            "title": self.title,
            "x_axis": self.x_axis_label,
            "y_axis": self.y_axis_label,
            "series": self.data_series,
            "legend": self.legend,
        }


@dataclass
class ExtractionResult:
    """提取结果"""
    success: bool
    tables: List[ExtractedTable] = field(default_factory=list)
    charts: List[ChartData] = field(default_factory=list)
    text_content: str = ""
    error: str = ""


class TableExtractor:
    """表格提取器"""
    
    def __init__(self, vision_service=None):
        self._vision_service = vision_service
    
    @property
    def vision_service(self):
        if self._vision_service is None:
            from .vision_service import get_vision_service
            self._vision_service = get_vision_service()
        return self._vision_service
    
    def extract_from_image(
        self,
        image_data: Union[bytes, str],
        extract_charts: bool = True,
    ) -> ExtractionResult:
        """
        从图片中提取表格和图表
        
        Args:
            image_data: 图片数据
            extract_charts: 是否提取图表
        
        Returns:
            ExtractionResult
        """
        try:
            tables = []
            charts = []
            
            # 提取表格
            table_result = self.vision_service.extract_tables(image_data)
            if table_result.success and table_result.tables:
                for t in table_result.tables:
                    tables.append(ExtractedTable(
                        title=t.get("title", ""),
                        headers=t.get("headers", []),
                        rows=t.get("rows", []),
                        confidence=0.9,
                    ))
            
            # 提取图表
            if extract_charts:
                chart_result = self.vision_service.analyze_chart(image_data)
                if chart_result.success and chart_result.charts:
                    for c in chart_result.charts:
                        charts.append(ChartData(
                            chart_type=c.get("type", "unknown"),
                            title=c.get("title", ""),
                            x_axis_label=c.get("x_axis", ""),
                            y_axis_label=c.get("y_axis", ""),
                            data_series=c.get("data", []),
                        ))
            
            return ExtractionResult(
                success=True,
                tables=tables,
                charts=charts,
                text_content=table_result.text_content or chart_result.text_content if extract_charts else table_result.text_content,
            )
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return ExtractionResult(success=False, error=str(e))
    
    def extract_from_pdf_page(
        self,
        pdf_bytes: bytes,
        page_number: int = 0,
    ) -> ExtractionResult:
        """
        从 PDF 页面提取表格
        
        Args:
            pdf_bytes: PDF 文件内容
            page_number: 页码（0-based）
        
        Returns:
            ExtractionResult
        """
        try:
            # 使用 pdf2image 转换 PDF 页面为图片
            try:
                from pdf2image import convert_from_bytes
                
                images = convert_from_bytes(
                    pdf_bytes,
                    first_page=page_number + 1,
                    last_page=page_number + 1,
                    dpi=200,
                )
                
                if not images:
                    return ExtractionResult(
                        success=False,
                        error=f"无法读取 PDF 第 {page_number + 1} 页",
                    )
                
                # 转换为 bytes
                img_buffer = BytesIO()
                images[0].save(img_buffer, format="PNG")
                img_bytes = img_buffer.getvalue()
                
                result = self.extract_from_image(img_bytes)
                for table in result.tables:
                    table.source_page = page_number
                
                return result
                
            except ImportError:
                logger.warning("pdf2image not installed, using fallback")
                return ExtractionResult(
                    success=False,
                    error="PDF 处理需要安装 pdf2image 库",
                )
                
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ExtractionResult(success=False, error=str(e))
    
    def parse_markdown_table(self, markdown_text: str) -> List[ExtractedTable]:
        """
        解析 Markdown 格式的表格
        
        Args:
            markdown_text: 包含表格的 Markdown 文本
        
        Returns:
            提取的表格列表
        """
        tables = []
        
        # 匹配 Markdown 表格
        table_pattern = r'\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)'
        
        for match in re.finditer(table_pattern, markdown_text):
            header_line = match.group(1)
            body_lines = match.group(2).strip()
            
            # 解析表头
            headers = [h.strip() for h in header_line.split("|") if h.strip()]
            
            # 解析数据行
            rows = []
            for line in body_lines.split("\n"):
                if line.strip():
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    if cells:
                        rows.append(cells)
            
            if headers or rows:
                tables.append(ExtractedTable(
                    headers=headers,
                    rows=rows,
                ))
        
        return tables
    
    def merge_tables(self, tables: List[ExtractedTable]) -> ExtractedTable:
        """
        合并多个相似结构的表格
        
        Args:
            tables: 要合并的表格列表
        
        Returns:
            合并后的表格
        """
        if not tables:
            return ExtractedTable()
        
        if len(tables) == 1:
            return tables[0]
        
        # 使用第一个表格的表头
        merged = ExtractedTable(
            title=tables[0].title or "合并表格",
            headers=tables[0].headers,
        )
        
        # 合并所有行
        for table in tables:
            merged.rows.extend(table.rows)
        
        return merged
    
    def table_to_parameters(self, table: ExtractedTable) -> List[Dict]:
        """
        将表格转换为参数列表（用于产品规格表）
        
        Args:
            table: 提取的表格
        
        Returns:
            参数列表 [{"name": "参数名", "value": "值", "unit": "单位"}, ...]
        """
        params = []
        
        # 检测表格结构
        if len(table.headers) == 2:
            # 两列：参数名 - 值
            for row in table.rows:
                if len(row) >= 2:
                    name = row[0]
                    value_str = row[1]
                    
                    # 尝试分离数值和单位
                    value, unit = self._parse_value_unit(value_str)
                    
                    params.append({
                        "name": name,
                        "value": value,
                        "unit": unit,
                        "raw": value_str,
                    })
        
        elif len(table.headers) >= 3:
            # 多列：可能是对比表
            for row in table.rows:
                if len(row) >= 2:
                    params.append({
                        "name": row[0],
                        "values": row[1:],
                        "headers": table.headers[1:],
                    })
        
        return params
    
    def _parse_value_unit(self, value_str: str) -> Tuple[str, str]:
        """从字符串中分离数值和单位"""
        
        # 常见单位模式
        unit_patterns = [
            r"([\d.]+)\s*(W|kW|MW|瓦|千瓦)",
            r"([\d.]+)\s*(V|mV|kV|伏|伏特)",
            r"([\d.]+)\s*(A|mA|安|安培)",
            r"([\d.]+)\s*(Hz|MHz|GHz|赫兹)",
            r"([\d.]+)\s*(m|mm|cm|km|米|毫米|厘米)",
            r"([\d.]+)\s*(kg|g|mg|千克|克)",
            r"([\d.]+)\s*(℃|°C|摄氏度)",
            r"([\d.]+)\s*(%|百分比)",
            r"([\d.]+)\s*(pcs|片|个|台|件)",
            r"([\d.]+)\s*(/h|/min|/s|每小时|每分钟|每秒)",
        ]
        
        for pattern in unit_patterns:
            match = re.search(pattern, value_str, re.IGNORECASE)
            if match:
                return match.group(1), match.group(2)
        
        return value_str, ""


# ==================== 模块级便捷函数 ====================

_default_extractor: Optional[TableExtractor] = None


def get_table_extractor() -> TableExtractor:
    """获取表格提取器实例"""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = TableExtractor()
    return _default_extractor


def extract_tables_from_image(image_data: Union[bytes, str]) -> ExtractionResult:
    """便捷函数：从图片提取表格"""
    return get_table_extractor().extract_from_image(image_data)


def table_to_markdown(table: ExtractedTable) -> str:
    """便捷函数：表格转 Markdown"""
    return table.to_markdown()

