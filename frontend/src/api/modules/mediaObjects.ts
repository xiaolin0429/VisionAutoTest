import { requestBlob, requestData } from '@/api/client'
import type { MediaObjectReadDTO } from '@/types/backend'
import type { MediaObject } from '@/types/models'

function mapMediaObject(item: MediaObjectReadDTO): MediaObject {
  return {
    id: item.id,
    workspaceId: item.workspace_id,
    storageType: item.storage_type,
    bucketName: item.bucket_name,
    objectKey: item.object_key,
    fileName: item.file_name,
    mimeType: item.mime_type,
    fileSize: item.file_size,
    checksumSha256: item.checksum_sha256,
    status: item.status,
    usage: item.usage,
    remark: item.remark ?? '',
    createdAt: item.created_at
  }
}

export async function createMediaObject(
  file: File,
  usage: string,
  remark?: string
): Promise<MediaObject> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('usage', usage)

  if (remark) {
    formData.append('remark', remark)
  }

  const response = await requestData<MediaObjectReadDTO>({
    method: 'post',
    url: '/media-objects',
    data: formData
  })

  return mapMediaObject(response)
}

export async function getMediaObject(mediaObjectId: number): Promise<MediaObject> {
  const response = await requestData<MediaObjectReadDTO>({
    method: 'get',
    url: `/media-objects/${mediaObjectId}`
  })

  return mapMediaObject(response)
}

export async function getMediaObjectContent(mediaObjectId: number): Promise<Blob> {
  return requestBlob({
    method: 'get',
    url: `/media-objects/${mediaObjectId}/content`
  })
}
