"""
视觉理解 API
图片上传、分析和问答
"""
import os
import uuid
import hashlib
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel

from ..auth import require_role
from ..services.vision_service import (
    get_vision_service,
    VisionService,
    VisionTaskType,
    VisionResult,
)
from ..services.table_extractor import (
    get_table_extractor,
    TableExtractor,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision", tags=["vision"])


# ==================== 请求/响应模型 ====================

class ImageAnalyzeRequest(BaseModel):
    """图片分析请求（URL方式）"""
    image_url: str
    question: Optional[str] = None
    task_type: str = "general_qa"


class ImageAnalyzeResponse(BaseModel):
    """图片分析响应"""
    success: bool
    task_type: str
    text_content: str = ""
    tables: List[dict] = []
    charts: List[dict] = []
    confidence: float = 0.0
    error: str = ""


class TableExtractionResponse(BaseModel):
    """表格提取响应"""
    success: bool
    tables: List[dict] = []
    table_count: int = 0
    markdown: str = ""
    error: str = ""


class VisionChatRequest(BaseModel):
    """视觉对话请求"""
    image_id: str
    question: str


class VisionChatResponse(BaseModel):
    """视觉对话响应"""
    success: bool
    answer: str = ""
    sources: List[dict] = []
    error: str = ""


# ==================== MinIO 图片存储辅助 ====================

def get_minio_client():
    """获取 MinIO 客户端"""
    try:
        from minio import Minio
        
        return Minio(
            os.getenv("MINIO_URL", "minio:9000").replace("http://", "").replace("https://", ""),
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=False,
        )
    except Exception as e:
        logger.error(f"Failed to create MinIO client: {e}")
        return None


def ensure_bucket(client, bucket_name: str):
    """确保 bucket 存在"""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except Exception as e:
        logger.error(f"Failed to ensure bucket {bucket_name}: {e}")


def save_image_to_minio(image_data: bytes, filename: str) -> Optional[str]:
    """保存图片到 MinIO"""
    client = get_minio_client()
    if not client:
        return None
    
    try:
        bucket_name = "images"
        ensure_bucket(client, bucket_name)
        
        # 生成唯一的对象名
        ext = os.path.splitext(filename)[1] or ".png"
        file_hash = hashlib.md5(image_data).hexdigest()[:8]
        object_name = f"{datetime.now().strftime('%Y%m%d')}/{file_hash}_{filename}"
        
        from io import BytesIO
        client.put_object(
            bucket_name,
            object_name,
            BytesIO(image_data),
            length=len(image_data),
            content_type=f"image/{ext.lstrip('.')}",
        )
        
        return f"{bucket_name}/{object_name}"
        
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return None


def get_image_from_minio(image_path: str) -> Optional[bytes]:
    """从 MinIO 获取图片"""
    client = get_minio_client()
    if not client:
        return None
    
    try:
        parts = image_path.split("/", 1)
        if len(parts) != 2:
            return None
        
        bucket_name, object_name = parts
        response = client.get_object(bucket_name, object_name)
        return response.read()
        
    except Exception as e:
        logger.error(f"Failed to get image: {e}")
        return None


# ==================== API 端点 ====================

@router.post("/upload", response_model=dict)
async def upload_image(
    file: UploadFile = File(...),
    analyze: bool = Form(default=False),
    extract_tables: bool = Form(default=False),
):
    """
    上传图片
    
    Args:
        file: 图片文件
        analyze: 是否立即分析
        extract_tables: 是否提取表格
    
    Returns:
        上传结果，包含图片ID和可选的分析结果
    """
    # 验证文件类型
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.content_type}",
        )
    
    # 读取文件内容
    image_data = await file.read()
    
    # 文件大小限制 (10MB)
    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过限制 (10MB)")
    
    # 保存到 MinIO
    image_path = save_image_to_minio(image_data, file.filename)
    if not image_path:
        raise HTTPException(status_code=500, detail="图片保存失败")
    
    result = {
        "success": True,
        "image_id": image_path,
        "filename": file.filename,
        "size": len(image_data),
        "content_type": file.content_type,
    }
    
    # 可选：立即分析
    if analyze:
        vision_service = get_vision_service()
        analysis = vision_service.analyze_image(image_data)
        result["analysis"] = {
            "text_content": analysis.text_content,
            "confidence": analysis.confidence,
        }
    
    # 可选：提取表格
    if extract_tables:
        extractor = get_table_extractor()
        extraction = extractor.extract_from_image(image_data)
        result["tables"] = [t.to_dict() for t in extraction.tables]
    
    return result


@router.post("/analyze", response_model=ImageAnalyzeResponse)
async def analyze_image(
    file: UploadFile = File(None),
    image_url: str = Form(None),
    question: str = Form(None),
    task_type: str = Form("general_qa"),
):
    """
    分析图片
    
    支持上传文件或提供图片URL
    """
    # 获取图片数据
    if file:
        image_data = await file.read()
    elif image_url:
        # 从URL获取图片
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法获取图片: {e}")
    else:
        raise HTTPException(status_code=400, detail="请提供图片文件或URL")
    
    # 解析任务类型
    try:
        task = VisionTaskType(task_type)
    except ValueError:
        task = VisionTaskType.GENERAL_QA
    
    # 分析图片
    vision_service = get_vision_service()
    result = vision_service.analyze_image(image_data, question, task)
    
    return ImageAnalyzeResponse(
        success=result.success,
        task_type=result.task_type.value,
        text_content=result.text_content,
        tables=[t for t in result.tables] if result.tables else [],
        charts=[c for c in result.charts] if result.charts else [],
        confidence=result.confidence,
        error=result.error,
    )


@router.post("/analyze-url", response_model=ImageAnalyzeResponse)
async def analyze_image_url(request: ImageAnalyzeRequest):
    """通过URL分析图片"""
    try:
        task = VisionTaskType(request.task_type)
    except ValueError:
        task = VisionTaskType.GENERAL_QA
    
    vision_service = get_vision_service()
    result = vision_service.analyze_image(
        request.image_url,
        request.question,
        task,
    )
    
    return ImageAnalyzeResponse(
        success=result.success,
        task_type=result.task_type.value,
        text_content=result.text_content,
        tables=result.tables,
        charts=result.charts,
        confidence=result.confidence,
        error=result.error,
    )


@router.post("/extract-tables", response_model=TableExtractionResponse)
async def extract_tables(
    file: UploadFile = File(...),
    output_format: str = Form("json"),
):
    """
    从图片中提取表格
    
    Args:
        file: 图片文件
        output_format: 输出格式 (json/markdown/csv)
    
    Returns:
        提取的表格数据
    """
    image_data = await file.read()
    
    extractor = get_table_extractor()
    result = extractor.extract_from_image(image_data, extract_charts=False)
    
    if not result.success:
        return TableExtractionResponse(
            success=False,
            error=result.error,
        )
    
    # 生成 Markdown 格式
    markdown_parts = []
    for table in result.tables:
        markdown_parts.append(table.to_markdown())
    
    return TableExtractionResponse(
        success=True,
        tables=[t.to_dict() for t in result.tables],
        table_count=len(result.tables),
        markdown="\n\n".join(markdown_parts),
    )


@router.post("/ask", response_model=VisionChatResponse)
async def ask_about_image(request: VisionChatRequest):
    """
    对已上传的图片提问
    
    Args:
        request: 包含图片ID和问题
    
    Returns:
        回答
    """
    # 从 MinIO 获取图片
    image_data = get_image_from_minio(request.image_id)
    if not image_data:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 调用视觉服务
    vision_service = get_vision_service()
    result = vision_service.ask_about_image(image_data, request.question)
    
    return VisionChatResponse(
        success=result.success,
        answer=result.text_content,
        error=result.error,
    )


@router.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    """
    OCR 文字识别
    
    Args:
        file: 图片文件
    
    Returns:
        识别的文字内容
    """
    image_data = await file.read()
    
    vision_service = get_vision_service()
    result = vision_service.ocr(image_data)
    
    return {
        "success": result.success,
        "text": result.text_content,
        "error": result.error,
    }


@router.post("/parse-document")
async def parse_document(file: UploadFile = File(...)):
    """
    解析文档图片
    
    Args:
        file: 文档图片
    
    Returns:
        文档结构和内容
    """
    image_data = await file.read()
    
    vision_service = get_vision_service()
    result = vision_service.parse_document(image_data)
    
    return {
        "success": result.success,
        "content": result.text_content,
        "structure": result.structured_data,
        "error": result.error,
    }


@router.get("/image/{image_id:path}")
async def get_image_info(image_id: str):
    """获取图片信息"""
    # 检查图片是否存在
    image_data = get_image_from_minio(image_id)
    if not image_data:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    return {
        "image_id": image_id,
        "size": len(image_data),
        "exists": True,
    }

