import axios from 'axios'
import { AUTH_SESSION_STORAGE_KEY } from '@/constants/storage'
import { API_BASE_URL, toApiError } from '@/api/shared'
import type {
  ApiEnvelope,
  CurrentSessionReadDTO,
  SessionRefreshResponseDTO,
  SessionResponseDTO
} from '@/types/backend'
import type {
  CurrentSession,
  SessionPayload,
  SessionRefreshPayload
} from '@/types/models'

interface StoredSession {
  accessToken?: string
  tokenType?: string
}

const authHttp = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000
})

function readStoredSession() {
  const raw = localStorage.getItem(AUTH_SESSION_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as StoredSession
  } catch {
    localStorage.removeItem(AUTH_SESSION_STORAGE_KEY)
    return null
  }
}

function createAuthorizationHeaders() {
  const storedSession = readStoredSession()
  if (!storedSession?.accessToken) {
    return undefined
  }

  return {
    Authorization: `${storedSession.tokenType ?? 'Bearer'} ${storedSession.accessToken}`
  }
}

function mapUser(item: { id: number; username: string; display_name: string }) {
  return {
    id: item.id,
    username: item.username,
    displayName: item.display_name
  }
}

export async function createSession(payload: {
  username: string
  password: string
}): Promise<SessionPayload> {
  try {
    const response = await authHttp.request<ApiEnvelope<SessionResponseDTO>>({
      method: 'post',
      url: '/sessions',
      data: payload
    })

    return {
      sessionId: response.data.data.session_id,
      accessToken: response.data.data.access_token,
      refreshToken: response.data.data.refresh_token,
      tokenType: response.data.data.token_type,
      expiresIn: response.data.data.expires_in,
      issuedAt: Date.now(),
      user: mapUser(response.data.data.user)
    }
  } catch (error) {
    throw toApiError(error)
  }
}

export async function refreshSession(refreshToken: string): Promise<SessionRefreshPayload> {
  try {
    const response = await authHttp.request<ApiEnvelope<SessionRefreshResponseDTO>>({
      method: 'post',
      url: '/session-refreshes',
      data: {
        refresh_token: refreshToken
      }
    })

    return {
      accessToken: response.data.data.access_token,
      refreshToken: response.data.data.refresh_token,
      tokenType: response.data.data.token_type,
      expiresIn: response.data.data.expires_in,
      issuedAt: Date.now()
    }
  } catch (error) {
    throw toApiError(error)
  }
}

export async function getCurrentSession(): Promise<CurrentSession> {
  try {
    const response = await authHttp.request<ApiEnvelope<CurrentSessionReadDTO>>({
      method: 'get',
      url: '/sessions/current',
      headers: createAuthorizationHeaders()
    })

    return {
      sessionId: response.data.data.session_id,
      status: response.data.data.status,
      expiresAt: response.data.data.expires_at,
      user: mapUser(response.data.data.user)
    }
  } catch (error) {
    throw toApiError(error)
  }
}

export async function deleteCurrentSession(): Promise<void> {
  try {
    await authHttp.request({
      method: 'delete',
      url: '/sessions/current',
      headers: createAuthorizationHeaders(),
      responseType: 'text'
    })
  } catch (error) {
    throw toApiError(error)
  }
}
