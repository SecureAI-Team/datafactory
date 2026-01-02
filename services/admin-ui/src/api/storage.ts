import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Get auth headers
const getAuthHeaders = () => {
  const token = localStorage.getItem('admin_access_token')
  return {
    Authorization: `Bearer ${token}`,
  }
}

// ==================== Types ====================

export interface StorageObject {
  name: string
  path: string
  size: number
  last_modified: string | null
  is_dir: boolean
  is_new: boolean
  mime_type: string | null
  etag: string | null
}

export interface BucketInfo {
  name: string
  creation_date: string | null
  object_count?: number
  total_size?: number
}

export interface ObjectListResponse {
  bucket: string
  prefix: string
  objects: StorageObject[]
  total: number
}

export interface MoveRequest {
  source_path: string
  destination_path: string
  destination_bucket?: string
}

export interface ArchiveRequest {
  paths: string[]
  archive_reason?: string
}

export interface TrashRequest {
  paths: string[]
}

export interface ProcessRequest {
  bucket: string
  paths: string[]
  dag_id: string
}

export interface StorageStats {
  buckets: BucketInfo[]
  total_objects: number
  total_size: number
  new_files_count: number
}

export interface UploadResult {
  message: string
  bucket: string
  path: string
  size: number
}

export interface DeleteResult {
  message: string
  deleted: number
  errors?: string[]
}

export interface TrashResult {
  message: string
  trashed: number
  trash_bucket: string
  timestamp: string
  errors?: string[]
}

export interface ArchiveResult {
  message: string
  archived: number
  archive_bucket: string
  timestamp: string
  errors?: string[]
}

export interface DownloadUrlResult {
  url: string
  expires_in: number
  filename: string
}

export interface PreviewResult {
  preview: string | null
  mime_type?: string
  size?: number
  truncated?: boolean
  message?: string
}

export interface ProcessResult {
  success: boolean
  message: string
  dag_run_id?: string
  files_count?: number
}

// ==================== API Functions ====================

export const storageApi = {
  /**
   * List all buckets
   */
  listBuckets: async (): Promise<BucketInfo[]> => {
    const response = await axios.get(`${API_BASE}/api/storage/buckets`, {
      headers: getAuthHeaders(),
    })
    return response.data
  },

  /**
   * List objects in a bucket
   */
  listObjects: async (
    bucket: string,
    prefix: string = '',
    recursive: boolean = false
  ): Promise<ObjectListResponse> => {
    const response = await axios.get(
      `${API_BASE}/api/storage/buckets/${bucket}/objects`,
      {
        params: { prefix, recursive },
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Upload a file to a bucket
   */
  uploadObject: async (
    bucket: string,
    file: File,
    prefix: string = ''
  ): Promise<UploadResult> => {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/${bucket}/objects`,
      formData,
      {
        params: { prefix },
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return response.data
  },

  /**
   * Delete objects from a bucket
   */
  deleteObjects: async (
    bucket: string,
    paths: string[]
  ): Promise<DeleteResult> => {
    const response = await axios.delete(
      `${API_BASE}/api/storage/buckets/${bucket}/objects`,
      {
        params: { paths },
        headers: getAuthHeaders(),
        paramsSerializer: {
          indexes: null, // Use paths=a&paths=b format
        },
      }
    )
    return response.data
  },

  /**
   * Move/rename an object
   */
  moveObject: async (
    bucket: string,
    sourcePath: string,
    destinationPath: string,
    destinationBucket?: string
  ): Promise<{ message: string; source: string; destination: string }> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/${bucket}/objects/move`,
      {
        source_path: sourcePath,
        destination_path: destinationPath,
        destination_bucket: destinationBucket,
      },
      {
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Archive objects
   */
  archiveObjects: async (
    bucket: string,
    paths: string[],
    archiveReason?: string
  ): Promise<ArchiveResult> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/${bucket}/objects/archive`,
      {
        paths,
        archive_reason: archiveReason,
      },
      {
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Move objects to trash
   */
  trashObjects: async (
    bucket: string,
    paths: string[]
  ): Promise<TrashResult> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/${bucket}/objects/trash`,
      { paths },
      {
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Restore objects from trash
   */
  restoreFromTrash: async (
    paths: string[]
  ): Promise<{ message: string; restored: number; errors?: string[] }> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/trash/objects/restore`,
      null,
      {
        params: { paths },
        headers: getAuthHeaders(),
        paramsSerializer: {
          indexes: null,
        },
      }
    )
    return response.data
  },

  /**
   * Create a directory
   */
  createDirectory: async (
    bucket: string,
    path: string
  ): Promise<{ message: string; bucket: string; path: string }> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/buckets/${bucket}/directories`,
      { path },
      {
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Get presigned download URL
   */
  getDownloadUrl: async (
    bucket: string,
    path: string
  ): Promise<DownloadUrlResult> => {
    const response = await axios.get(
      `${API_BASE}/api/storage/buckets/${bucket}/download`,
      {
        params: { path },
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Preview file content
   */
  previewObject: async (
    bucket: string,
    path: string,
    maxSize: number = 102400
  ): Promise<PreviewResult> => {
    const response = await axios.get(
      `${API_BASE}/api/storage/buckets/${bucket}/preview`,
      {
        params: { path, max_size: maxSize },
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Trigger file processing pipeline
   */
  processFiles: async (
    bucket: string,
    paths: string[],
    dagId: string = 'ingest_to_bronze'
  ): Promise<ProcessResult> => {
    const response = await axios.post(
      `${API_BASE}/api/storage/process`,
      {
        bucket,
        paths,
        dag_id: dagId,
      },
      {
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },

  /**
   * Get storage statistics
   */
  getStats: async (): Promise<StorageStats> => {
    const response = await axios.get(`${API_BASE}/api/storage/stats`, {
      headers: getAuthHeaders(),
    })
    return response.data
  },

  /**
   * Empty trash (admin only)
   */
  emptyTrash: async (
    olderThanDays: number = 30
  ): Promise<{ message: string; deleted: number }> => {
    const response = await axios.delete(
      `${API_BASE}/api/storage/buckets/trash/trash/empty`,
      {
        params: { older_than_days: olderThanDays },
        headers: getAuthHeaders(),
      }
    )
    return response.data
  },
}

export default storageApi

