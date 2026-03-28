import { requestData, requestPage } from '@/api/client'
import type {
  DeviceProfileReadDTO,
  EnvironmentProfileReadDTO,
  EnvironmentVariableReadDTO
} from '@/types/backend'
import type { DeviceProfile, EnvironmentProfile } from '@/types/models'

export async function listEnvironmentProfiles(): Promise<EnvironmentProfile[]> {
  const response = await requestPage<EnvironmentProfileReadDTO>({
    method: 'get',
    url: '/environment-profiles',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return Promise.all(
    response.data.map(async (item) => {
      const variables = await requestData<EnvironmentVariableReadDTO[]>({
        method: 'get',
        url: `/environment-profiles/${item.id}/variables`
      })

      return {
        id: item.id,
        workspaceId: item.workspace_id,
        name: item.profile_name,
        baseUrl: item.base_url,
        description: item.description ?? '',
        status: item.status,
        variableCount: variables.length,
        createdAt: item.created_at,
        updatedAt: item.updated_at
      }
    })
  )
}

export async function listDeviceProfiles(): Promise<DeviceProfile[]> {
  const response = await requestPage<DeviceProfileReadDTO>({
    method: 'get',
    url: '/device-profiles',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return response.data.map((item) => ({
    id: item.id,
    workspaceId: item.workspace_id,
    name: item.profile_name,
    platform: item.device_type,
    width: item.viewport_width,
    height: item.viewport_height,
    pixelRatio: Number(item.device_scale_factor),
    userAgent: item.user_agent ?? undefined,
    isDefault: item.is_default,
    createdAt: item.created_at,
    updatedAt: item.updated_at
  }))
}
