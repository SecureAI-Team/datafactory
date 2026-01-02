"""Storage management API endpoints for MinIO"""
import os
import io
import mimetypes
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User
from ..clients.minio_client import get_client as get_minio_client
from .auth import require_role

router = APIRouter(prefix="/api/storage", tags=["storage"])


# ==================== Request/Response Models ====================

class StorageObject(BaseModel):
    name: str
    path: str
    size: int
    last_modified: Optional[str]
    is_dir: bool
    is_new: bool  # Files uploaded within 24 hours
    mime_type: Optional[str]
    etag: Optional[str]


class BucketInfo(BaseModel):
    name: str
    creation_date: Optional[str]
    object_count: Optional[int] = None
    total_size: Optional[int] = None


class ObjectListResponse(BaseModel):
    bucket: str
    prefix: str
    objects: List[StorageObject]
    total: int


class MoveRequest(BaseModel):
    source_path: str
    destination_path: str
    destination_bucket: Optional[str] = None


class ArchiveRequest(BaseModel):
    paths: List[str]
    archive_reason: Optional[str] = None


class TrashRequest(BaseModel):
    paths: List[str]


class CreateDirectoryRequest(BaseModel):
    path: str


class ProcessRequest(BaseModel):
    bucket: str
    paths: List[str]
    dag_id: str = "ingest_to_bronze"


class StorageStatsResponse(BaseModel):
    buckets: List[BucketInfo]
    total_objects: int
    total_size: int
    new_files_count: int  # Files in last 24 hours


# ==================== Helper Functions ====================

def is_new_file(last_modified: datetime) -> bool:
    """Check if file was uploaded within last 24 hours"""
    if not last_modified:
        return False
    now = datetime.now(timezone.utc)
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    return (now - last_modified).total_seconds() < 86400


def get_mime_type(filename: str) -> str:
    """Get MIME type from filename"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def format_size(size: int) -> str:
    """Format size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def ensure_bucket_exists(minio_client, bucket_name: str):
    """Ensure bucket exists, create if not"""
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)


# ==================== API Endpoints ====================

@router.get("/buckets", response_model=List[BucketInfo])
async def list_buckets(
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """List all MinIO buckets"""
    try:
        minio_client = get_minio_client()
        buckets = minio_client.list_buckets()
        
        result = []
        for bucket in buckets:
            result.append(BucketInfo(
                name=bucket.name,
                creation_date=bucket.creation_date.isoformat() if bucket.creation_date else None
            ))
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list buckets: {str(e)}"
        )


@router.get("/buckets/{bucket}/objects", response_model=ObjectListResponse)
async def list_objects(
    bucket: str,
    prefix: str = "",
    recursive: bool = False,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """List objects in a bucket with optional prefix filter"""
    try:
        minio_client = get_minio_client()
        
        if not minio_client.bucket_exists(bucket):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bucket '{bucket}' not found"
            )
        
        # List objects
        objects = minio_client.list_objects(
            bucket,
            prefix=prefix,
            recursive=recursive
        )
        
        result = []
        seen_dirs = set()
        
        for obj in objects:
            # Handle directories (prefixes)
            if obj.is_dir:
                dir_name = obj.object_name.rstrip('/').split('/')[-1]
                if dir_name not in seen_dirs:
                    seen_dirs.add(dir_name)
                    result.append(StorageObject(
                        name=dir_name,
                        path=obj.object_name,
                        size=0,
                        last_modified=None,
                        is_dir=True,
                        is_new=False,
                        mime_type=None,
                        etag=None
                    ))
            else:
                # Regular file
                file_name = obj.object_name.split('/')[-1]
                result.append(StorageObject(
                    name=file_name,
                    path=obj.object_name,
                    size=obj.size or 0,
                    last_modified=obj.last_modified.isoformat() if obj.last_modified else None,
                    is_dir=False,
                    is_new=is_new_file(obj.last_modified) if obj.last_modified else False,
                    mime_type=get_mime_type(file_name),
                    etag=obj.etag
                ))
        
        # Sort: directories first, then by name
        result.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        return ObjectListResponse(
            bucket=bucket,
            prefix=prefix,
            objects=result,
            total=len(result)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list objects: {str(e)}"
        )


@router.post("/buckets/{bucket}/objects")
async def upload_object(
    bucket: str,
    file: UploadFile = File(...),
    prefix: str = "",
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Upload a file to bucket"""
    try:
        minio_client = get_minio_client()
        ensure_bucket_exists(minio_client, bucket)
        
        # Build object path
        object_name = f"{prefix.rstrip('/')}/{file.filename}" if prefix else file.filename
        object_name = object_name.lstrip('/')
        
        # Get file content
        content = await file.read()
        content_type = file.content_type or get_mime_type(file.filename)
        
        # Upload to MinIO
        minio_client.put_object(
            bucket,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type=content_type
        )
        
        return {
            "message": "File uploaded successfully",
            "bucket": bucket,
            "path": object_name,
            "size": len(content)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.delete("/buckets/{bucket}/objects")
async def delete_objects(
    bucket: str,
    paths: List[str] = Query(...),
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Delete objects from bucket (permanently)"""
    try:
        minio_client = get_minio_client()
        
        if not minio_client.bucket_exists(bucket):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bucket '{bucket}' not found"
            )
        
        deleted = 0
        errors = []
        
        for path in paths:
            try:
                # Check if it's a directory (ends with /)
                if path.endswith('/'):
                    # Delete all objects with this prefix
                    objects = list(minio_client.list_objects(bucket, prefix=path, recursive=True))
                    for obj in objects:
                        minio_client.remove_object(bucket, obj.object_name)
                        deleted += 1
                else:
                    minio_client.remove_object(bucket, path)
                    deleted += 1
            except Exception as e:
                errors.append(f"{path}: {str(e)}")
        
        return {
            "message": f"Deleted {deleted} objects",
            "deleted": deleted,
            "errors": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete objects: {str(e)}"
        )


@router.post("/buckets/{bucket}/objects/move")
async def move_object(
    bucket: str,
    body: MoveRequest,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Move or rename an object"""
    try:
        minio_client = get_minio_client()
        
        dest_bucket = body.destination_bucket or bucket
        ensure_bucket_exists(minio_client, dest_bucket)
        
        # Copy to new location
        minio_client.copy_object(
            dest_bucket,
            body.destination_path,
            f"/{bucket}/{body.source_path}"
        )
        
        # Remove original
        minio_client.remove_object(bucket, body.source_path)
        
        return {
            "message": "Object moved successfully",
            "source": f"{bucket}/{body.source_path}",
            "destination": f"{dest_bucket}/{body.destination_path}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to move object: {str(e)}"
        )


@router.post("/buckets/{bucket}/objects/archive")
async def archive_objects(
    bucket: str,
    body: ArchiveRequest,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Move objects to archive bucket"""
    try:
        minio_client = get_minio_client()
        ensure_bucket_exists(minio_client, "archive")
        
        archived = 0
        errors = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for path in body.paths:
            try:
                # Build archive path: archive/{original_bucket}/{timestamp}/{path}
                archive_path = f"{bucket}/{timestamp}/{path}"
                
                # Copy to archive
                minio_client.copy_object(
                    "archive",
                    archive_path,
                    f"/{bucket}/{path}"
                )
                
                # Remove original
                minio_client.remove_object(bucket, path)
                archived += 1
            except Exception as e:
                errors.append(f"{path}: {str(e)}")
        
        return {
            "message": f"Archived {archived} objects",
            "archived": archived,
            "archive_bucket": "archive",
            "timestamp": timestamp,
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive objects: {str(e)}"
        )


@router.post("/buckets/{bucket}/objects/trash")
async def trash_objects(
    bucket: str,
    body: TrashRequest,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Move objects to trash bucket (soft delete)"""
    try:
        minio_client = get_minio_client()
        ensure_bucket_exists(minio_client, "trash")
        
        trashed = 0
        errors = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for path in body.paths:
            try:
                # Build trash path: trash/{original_bucket}/{timestamp}/{path}
                trash_path = f"{bucket}/{timestamp}/{path}"
                
                # Copy to trash
                minio_client.copy_object(
                    "trash",
                    trash_path,
                    f"/{bucket}/{path}"
                )
                
                # Remove original
                minio_client.remove_object(bucket, path)
                trashed += 1
            except Exception as e:
                errors.append(f"{path}: {str(e)}")
        
        return {
            "message": f"Moved {trashed} objects to trash",
            "trashed": trashed,
            "trash_bucket": "trash",
            "timestamp": timestamp,
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trash objects: {str(e)}"
        )


@router.post("/buckets/{bucket}/objects/restore")
async def restore_from_trash(
    bucket: str,
    paths: List[str] = Query(..., description="Paths in trash bucket to restore"),
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Restore objects from trash bucket"""
    try:
        minio_client = get_minio_client()
        
        if not minio_client.bucket_exists("trash"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trash bucket not found"
            )
        
        restored = 0
        errors = []
        
        for trash_path in paths:
            try:
                # Parse trash path: {original_bucket}/{timestamp}/{original_path}
                parts = trash_path.split('/', 2)
                if len(parts) < 3:
                    errors.append(f"{trash_path}: Invalid trash path format")
                    continue
                
                original_bucket, _, original_path = parts
                
                ensure_bucket_exists(minio_client, original_bucket)
                
                # Copy back to original location
                minio_client.copy_object(
                    original_bucket,
                    original_path,
                    f"/trash/{trash_path}"
                )
                
                # Remove from trash
                minio_client.remove_object("trash", trash_path)
                restored += 1
            except Exception as e:
                errors.append(f"{trash_path}: {str(e)}")
        
        return {
            "message": f"Restored {restored} objects",
            "restored": restored,
            "errors": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore objects: {str(e)}"
        )


@router.post("/buckets/{bucket}/directories")
async def create_directory(
    bucket: str,
    body: CreateDirectoryRequest,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Create a directory (empty object with trailing slash)"""
    try:
        minio_client = get_minio_client()
        ensure_bucket_exists(minio_client, bucket)
        
        # Ensure path ends with /
        dir_path = body.path.rstrip('/') + '/'
        
        # Create empty object to represent directory
        minio_client.put_object(
            bucket,
            dir_path,
            io.BytesIO(b''),
            length=0
        )
        
        return {
            "message": "Directory created",
            "bucket": bucket,
            "path": dir_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create directory: {str(e)}"
        )


@router.get("/buckets/{bucket}/download")
async def get_download_url(
    bucket: str,
    path: str,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Get presigned download URL for an object"""
    try:
        minio_client = get_minio_client()
        
        if not minio_client.bucket_exists(bucket):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bucket '{bucket}' not found"
            )
        
        # Generate presigned URL (valid for 1 hour)
        url = minio_client.presigned_get_object(
            bucket,
            path,
            expires=timedelta(hours=1)
        )
        
        return {
            "url": url,
            "expires_in": 3600,
            "filename": path.split('/')[-1]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.get("/buckets/{bucket}/preview")
async def preview_object(
    bucket: str,
    path: str,
    max_size: int = 102400,  # 100KB default
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Get preview content of a text file"""
    try:
        minio_client = get_minio_client()
        
        # Get object info
        stat = minio_client.stat_object(bucket, path)
        
        # Check if file is too large
        if stat.size > max_size:
            return {
                "preview": None,
                "truncated": True,
                "size": stat.size,
                "message": f"File too large for preview ({format_size(stat.size)})"
            }
        
        # Check if it's a text file
        mime_type = get_mime_type(path)
        text_types = ['text/', 'application/json', 'application/xml', 'application/javascript']
        is_text = any(mime_type.startswith(t) for t in text_types)
        
        if not is_text:
            return {
                "preview": None,
                "mime_type": mime_type,
                "size": stat.size,
                "message": "Binary file - preview not available"
            }
        
        # Get content
        response = minio_client.get_object(bucket, path)
        content = response.read().decode('utf-8', errors='replace')
        response.close()
        response.release_conn()
        
        return {
            "preview": content,
            "mime_type": mime_type,
            "size": stat.size,
            "truncated": False
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview object: {str(e)}"
        )


@router.post("/process")
async def process_files(
    body: ProcessRequest,
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Trigger Airflow DAG to process selected files"""
    import httpx
    from ..config import settings
    
    try:
        # Trigger the DAG with file paths as conf
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.airflow_url}/api/v1/dags/{body.dag_id}/dagRuns",
                json={
                    "conf": {
                        "bucket": body.bucket,
                        "paths": body.paths,
                        "triggered_by": admin.username
                    }
                },
                auth=(settings.airflow_user, settings.airflow_password),
                timeout=30.0
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "message": f"Pipeline '{body.dag_id}' triggered successfully",
                    "dag_run_id": result.get("dag_run_id"),
                    "files_count": len(body.paths)
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to trigger pipeline: {response.text}"
                }
                
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到 Airflow 服务器"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error triggering pipeline: {str(e)}"
        }


@router.get("/stats", response_model=StorageStatsResponse)
async def get_storage_stats(
    admin: User = Depends(require_role("admin", "data_ops"))
):
    """Get storage statistics across all buckets"""
    try:
        minio_client = get_minio_client()
        buckets = minio_client.list_buckets()
        
        bucket_infos = []
        total_objects = 0
        total_size = 0
        new_files = 0
        
        for bucket in buckets:
            bucket_objects = 0
            bucket_size = 0
            
            try:
                for obj in minio_client.list_objects(bucket.name, recursive=True):
                    if not obj.is_dir:
                        bucket_objects += 1
                        bucket_size += obj.size or 0
                        if is_new_file(obj.last_modified):
                            new_files += 1
            except Exception:
                pass  # Skip inaccessible buckets
            
            bucket_infos.append(BucketInfo(
                name=bucket.name,
                creation_date=bucket.creation_date.isoformat() if bucket.creation_date else None,
                object_count=bucket_objects,
                total_size=bucket_size
            ))
            
            total_objects += bucket_objects
            total_size += bucket_size
        
        return StorageStatsResponse(
            buckets=bucket_infos,
            total_objects=total_objects,
            total_size=total_size,
            new_files_count=new_files
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage stats: {str(e)}"
        )


@router.delete("/buckets/{bucket}/trash/empty")
async def empty_trash(
    bucket: str = "trash",
    older_than_days: int = 30,
    admin: User = Depends(require_role("admin"))
):
    """Empty trash bucket (delete files older than specified days)"""
    try:
        minio_client = get_minio_client()
        
        if not minio_client.bucket_exists("trash"):
            return {"message": "Trash bucket is empty", "deleted": 0}
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        deleted = 0
        
        for obj in minio_client.list_objects("trash", recursive=True):
            if obj.last_modified and obj.last_modified < cutoff:
                minio_client.remove_object("trash", obj.object_name)
                deleted += 1
        
        return {
            "message": f"Emptied trash: deleted {deleted} objects older than {older_than_days} days",
            "deleted": deleted
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to empty trash: {str(e)}"
        )

