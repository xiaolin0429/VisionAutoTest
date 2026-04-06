import { requestData, requestPage, requestVoid } from '@/api/client'
import type {
  DeviceProfileReadDTO,
  EnvironmentProfileReadDTO,
  EnvironmentVariableReadDTO
} from '@/types/backend'
import type {
  DeviceProfile,
  DeviceProfileCreatePayload,
  DeviceProfileUpdatePayload,
  EnvironmentProfile,
  EnvironmentProfileCreatePayload,
  EnvironmentProfileUpdatePayload,
  EnvironmentVariable,
  EnvironmentVariableCreatePayload,
  EnvironmentVariableUpdatePayload
} from '@/types/models'

function mapEnvironmentVariable(item: EnvironmentVariableReadDTO): EnvironmentVariable {
  // @param item Backend environment-variable DTO with masked/decrypted display_value already resolved server-side.
  return {
    id: item.id,
    environmentProfileId: item.environment_profile_id,
    key: item.var_key,
    isSecret: item.is_secret,
    description: item.description ?? '',
    displayValue: item.display_value ?? '',
    createdAt: item.created_at,
    updatedAt: item.updated_at
  }
}

export async function listEnvironmentProfiles(): Promise<EnvironmentProfile[]> {
  // Loads profile summaries, then enriches each profile with variableCount from the profile-scoped variables API.
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

export async function createEnvironmentProfile(
  payload: EnvironmentProfileCreatePayload
): Promise<EnvironmentProfile> {
  // @param payload Frontend create payload for an environment profile.
  const item = await requestData<EnvironmentProfileReadDTO>({
    method: 'post',
    url: '/environment-profiles',
    data: {
      profile_name: payload.name,
      base_url: payload.baseUrl,
      description: payload.description,
      status: payload.status
    }
  })

  return {
    id: item.id,
    workspaceId: item.workspace_id,
    name: item.profile_name,
    baseUrl: item.base_url,
    description: item.description ?? '',
    status: item.status,
    variableCount: 0,
    createdAt: item.created_at,
    updatedAt: item.updated_at
  }
}

export async function updateEnvironmentProfile(
  environmentProfileId: number,
  payload: EnvironmentProfileUpdatePayload
): Promise<EnvironmentProfile> {
  // @param environmentProfileId Environment-profile id being updated.
  // @param payload Frontend update payload.
  const item = await requestData<EnvironmentProfileReadDTO>({
    method: 'patch',
    url: `/environment-profiles/${environmentProfileId}`,
    data: {
      profile_name: payload.name,
      base_url: payload.baseUrl,
      description: payload.description,
      status: payload.status
    }
  })

  const variables = await listEnvironmentVariables(environmentProfileId)

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
}

export async function deleteEnvironmentProfile(environmentProfileId: number): Promise<void> {
  await requestVoid({
    method: 'delete',
    url: `/environment-profiles/${environmentProfileId}`
  })
}

export async function listEnvironmentVariables(
  environmentProfileId: number
): Promise<EnvironmentVariable[]> {
  // @param environmentProfileId Parent environment-profile id.
  const response = await requestData<EnvironmentVariableReadDTO[]>({
    method: 'get',
    url: `/environment-profiles/${environmentProfileId}/variables`
  })

  return response.map(mapEnvironmentVariable)
}

export async function createEnvironmentVariable(
  environmentProfileId: number,
  payload: EnvironmentVariableCreatePayload
): Promise<EnvironmentVariable> {
  // @param environmentProfileId Parent environment-profile id.
  // @param payload Frontend create payload for one environment variable.
  const response = await requestData<EnvironmentVariableReadDTO>({
    method: 'post',
    url: `/environment-profiles/${environmentProfileId}/variables`,
    data: {
      var_key: payload.key,
      value: payload.value,
      is_secret: payload.isSecret,
      description: payload.description
    }
  })

  return mapEnvironmentVariable(response)
}

export async function updateEnvironmentVariable(
  environmentVariableId: number,
  payload: EnvironmentVariableUpdatePayload
): Promise<EnvironmentVariable> {
  // @param environmentVariableId Environment-variable id being updated.
  // @param payload Frontend update payload for one variable.
  const response = await requestData<EnvironmentVariableReadDTO>({
    method: 'patch',
    url: `/environment-variables/${environmentVariableId}`,
    data: {
      value: payload.value,
      is_secret: payload.isSecret,
      description: payload.description
    }
  })

  return mapEnvironmentVariable(response)
}

export async function deleteEnvironmentVariable(environmentVariableId: number): Promise<void> {
  await requestVoid({
    method: 'delete',
    url: `/environment-variables/${environmentVariableId}`
  })
}

export async function listDeviceProfiles(): Promise<DeviceProfile[]> {
  // Loads device-profile summaries for suite/run trigger forms and environment management.
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

function mapDeviceProfile(item: DeviceProfileReadDTO): DeviceProfile {
  // @param item Backend device-profile DTO.
  return {
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
  }
}

export async function createDeviceProfile(
  payload: DeviceProfileCreatePayload
): Promise<DeviceProfile> {
  // @param payload Frontend create payload for a device profile.
  const response = await requestData<DeviceProfileReadDTO>({
    method: 'post',
    url: '/device-profiles',
    data: {
      profile_name: payload.name,
      device_type: payload.platform,
      viewport_width: payload.width,
      viewport_height: payload.height,
      device_scale_factor: payload.pixelRatio,
      user_agent: payload.userAgent,
      is_default: payload.isDefault
    }
  })

  return mapDeviceProfile(response)
}

export async function updateDeviceProfile(
  deviceProfileId: number,
  payload: DeviceProfileUpdatePayload
): Promise<DeviceProfile> {
  // @param deviceProfileId Device-profile id being updated.
  // @param payload Frontend update payload.
  const response = await requestData<DeviceProfileReadDTO>({
    method: 'patch',
    url: `/device-profiles/${deviceProfileId}`,
    data: {
      profile_name: payload.name,
      device_type: payload.platform,
      viewport_width: payload.width,
      viewport_height: payload.height,
      device_scale_factor: payload.pixelRatio,
      user_agent: payload.userAgent,
      is_default: payload.isDefault
    }
  })

  return mapDeviceProfile(response)
}
