import { requestData, requestVoid } from '@/api/client'
import type { SessionResponseDTO } from '@/types/backend'
import type { SessionPayload } from '@/types/models'

export async function createSession(payload: {
  username: string
  password: string
}): Promise<SessionPayload> {
  const response = await requestData<SessionResponseDTO>({
    method: 'post',
    url: '/sessions',
    data: payload
  })

  return {
    sessionId: response.session_id,
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    expiresIn: response.expires_in,
    user: {
      id: response.user.id,
      username: response.user.username,
      displayName: response.user.display_name
    }
  }
}

export async function deleteCurrentSession(): Promise<void> {
  await requestVoid({
    method: 'delete',
    url: '/sessions/current'
  })
}
