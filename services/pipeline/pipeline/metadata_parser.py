"""
路径元数据解析器
从上传路径中提取场景、解决方案等元数据信息
"""
import os
import json
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FileMetadata:
    """文件元数据"""
    # 路径信息
    original_path: str
    filename: str
    file_extension: str
    
    # 场景信息（从路径提取）
    scenario_id: Optional[str] = None
    solution_id: Optional[str] = None
    
    # 处理状态
    upload_time: str = ""
    processed: bool = False
    
    # 手动标注（从metadata.json读取）
    manual_scenario_tags: list = None
    manual_intent_types: list = None
    manual_material_type: str = None
    manual_applicability_score: float = None
    
    def __post_init__(self):
        if self.manual_scenario_tags is None:
            self.manual_scenario_tags = []
        if self.manual_intent_types is None:
            self.manual_intent_types = []
        if not self.upload_time:
            self.upload_time = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# 已知场景ID列表（用于验证）
KNOWN_SCENARIOS = {
    # 工业智能
    "aoi_inspection": "AOI视觉检测",
    "industrial_robot": "工业机器人",
    "predictive_maintenance": "预测性维护",
    "quality_control": "质量管理",
    
    # 安全
    "network_security": "网络安全",
    "data_security": "数据安全",
    "cloud_security": "云安全",
    
    # 通用
    "common": "通用材料",
    "general": "通用",
}

# 场景ID别名映射
SCENARIO_ALIASES = {
    "aoi": "aoi_inspection",
    "视觉检测": "aoi_inspection",
    "机器人": "industrial_robot",
    "robot": "industrial_robot",
    "预测维护": "predictive_maintenance",
    "pm": "predictive_maintenance",
    "网安": "network_security",
    "netsec": "network_security",
    "数安": "data_security",
    "datasec": "data_security",
}


def normalize_scenario_id(raw_id: str) -> str:
    """
    标准化场景ID
    """
    if not raw_id:
        return ""
    
    # 转小写，替换空格和横杠
    normalized = raw_id.lower().strip()
    normalized = re.sub(r'[\s\-]+', '_', normalized)
    
    # 检查别名
    if normalized in SCENARIO_ALIASES:
        return SCENARIO_ALIASES[normalized]
    
    # 检查是否是已知场景
    if normalized in KNOWN_SCENARIOS:
        return normalized
    
    # 返回原始值（可能是新场景）
    return normalized


def parse_upload_path(path: str) -> FileMetadata:
    """
    解析上传路径，提取元数据
    
    路径格式：
    - uploads/{scenario_id}/{solution_id}/{filename}
    - uploads/{scenario_id}/general/{filename}
    - uploads/common/{filename}
    - uploads/{filename}
    
    Args:
        path: 上传路径（相对于MinIO bucket根目录）
        
    Returns:
        FileMetadata 对象
    """
    # 标准化路径分隔符
    path = path.replace('\\', '/')
    
    # 移除开头的 uploads/ 或 /
    if path.startswith('uploads/'):
        path = path[8:]
    elif path.startswith('/'):
        path = path[1:]
    
    # 分解路径
    parts = [p for p in path.split('/') if p]
    
    if not parts:
        raise ValueError(f"Invalid path: {path}")
    
    # 提取文件名和扩展名
    filename = parts[-1]
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # 解析场景和解决方案
    scenario_id = None
    solution_id = None
    
    if len(parts) >= 3:
        # uploads/{scenario}/{solution}/{file}
        scenario_id = normalize_scenario_id(parts[0])
        solution_id = parts[1]
    elif len(parts) == 2:
        # uploads/{scenario}/{file} 或 uploads/common/{file}
        first_part = parts[0].lower()
        if first_part == "common":
            scenario_id = "common"
            solution_id = None
        else:
            scenario_id = normalize_scenario_id(parts[0])
            solution_id = "general"
    elif len(parts) == 1:
        # uploads/{file} - 无场景
        scenario_id = None
        solution_id = None
    
    return FileMetadata(
        original_path=path,
        filename=filename,
        file_extension=ext,
        scenario_id=scenario_id,
        solution_id=solution_id,
    )


def load_manual_metadata(
    minio_client,
    bucket: str,
    path: str
) -> Optional[Dict[str, Any]]:
    """
    尝试加载同目录下的 metadata.json
    
    Args:
        minio_client: MinIO客户端
        bucket: bucket名称
        path: 文件路径
        
    Returns:
        元数据字典，如果不存在返回None
    """
    import tempfile
    
    # 构建metadata.json路径
    dir_path = os.path.dirname(path)
    metadata_path = os.path.join(dir_path, "metadata.json").replace('\\', '/')
    
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            minio_client.fget_object(bucket, metadata_path, tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                data = json.load(f)
            os.unlink(tmp.name)
            return data
    except Exception:
        return None


def merge_metadata(
    file_meta: FileMetadata,
    manual_meta: Optional[Dict[str, Any]]
) -> FileMetadata:
    """
    合并文件元数据和手动标注
    
    Args:
        file_meta: 从路径解析的元数据
        manual_meta: 从metadata.json读取的手动标注
        
    Returns:
        合并后的FileMetadata
    """
    if not manual_meta:
        return file_meta
    
    # 手动标注优先级更高
    if manual_meta.get("scenario_id"):
        file_meta.scenario_id = normalize_scenario_id(manual_meta["scenario_id"])
    
    if manual_meta.get("solution_id"):
        file_meta.solution_id = manual_meta["solution_id"]
    
    if manual_meta.get("scenario_tags"):
        file_meta.manual_scenario_tags = manual_meta["scenario_tags"]
    
    if manual_meta.get("intent_types"):
        file_meta.manual_intent_types = manual_meta["intent_types"]
    
    if manual_meta.get("material_type"):
        file_meta.manual_material_type = manual_meta["material_type"]
    
    if manual_meta.get("applicability_score") is not None:
        file_meta.manual_applicability_score = float(manual_meta["applicability_score"])
    
    return file_meta


def generate_metadata_path(original_path: str) -> str:
    """
    生成元数据存储路径
    
    Args:
        original_path: 原始文件路径
        
    Returns:
        bronze/metadata/ 下的元数据文件路径
    """
    # 移除扩展名，添加.meta.json
    base_name = os.path.basename(original_path)
    name, _ = os.path.splitext(base_name)
    
    # 保持目录结构
    dir_path = os.path.dirname(original_path)
    
    return f"metadata/{dir_path}/{name}.meta.json".replace('//', '/')


# 测试代码
if __name__ == "__main__":
    test_paths = [
        "uploads/aoi_inspection/pcb_detection/spec.pdf",
        "uploads/aoi_inspection/general/overview.pdf",
        "uploads/network_security/defense_in_depth/whitepaper.pdf",
        "uploads/common/industry_standards.pdf",
        "uploads/document.pdf",
        "aoi_inspection/pcb_detection/guide.docx",
    ]
    
    for path in test_paths:
        print(f"\n路径: {path}")
        try:
            meta = parse_upload_path(path)
            print(f"  文件名: {meta.filename}")
            print(f"  扩展名: {meta.file_extension}")
            print(f"  场景ID: {meta.scenario_id}")
            print(f"  方案ID: {meta.solution_id}")
            print(f"  元数据路径: {generate_metadata_path(meta.original_path)}")
        except Exception as e:
            print(f"  错误: {e}")

