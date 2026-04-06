import { requestBlob, requestData } from '@/api/client'
import type { MediaObjectReadDTO } from '@/types/backend'
import type { MediaObject } from '@/types/models'

function mapMediaObject(item: MediaObjectReadDTO): MediaObject {
  // @param item Backend media-object DTO.
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
  // @param file Browser file chosen for upload.
  // @param usage Business usage tag such as template, artifact, or baseline.
  // @param remark Optional operator-facing remark saved with the media object.
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
  // @param mediaObjectId Media-object id whose metadata should be loaded.
  const response = await requestData<MediaObjectReadDTO>({
    method: 'get',
    url: `/media-objects/${mediaObjectId}`
  })

  return mapMediaObject(response)
}

export async function getMediaObjectContent(mediaObjectId: number): Promise<Blob> {
  // @param mediaObjectId Media-object id whose binary content should be downloaded.
  return requestBlob({
    method: 'get',
    url: `/media-objects/${mediaObjectId}/content`
  })
}
