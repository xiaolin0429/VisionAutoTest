import axios, {
  AxiosHeaders,
  type AxiosError,
  type AxiosRequestConfig
} from 'axios'
import {
  AUTH_SESSION_STORAGE_KEY,
  WORKSPACE_STORAGE_KEY
} from '@/constants/storage'
import type { ApiEnvelope, PaginatedEnvelope } from '@/types/backend'

interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: Array<Record<string, unknown>>
  }
}

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode?: number,
    public readonly details?: Array<Record<string, unknown>>
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 10000
})

function readStoredJson<T>(key: string): T | null {
  const raw = localStorage.getItem(key)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    localStorage.removeItem(key)
    return null
  }
}

http.interceptors.request.use((config) => {
  const storedSession = readStoredJson<{ accessToken?: string }>(AUTH_SESSION_STORAGE_KEY)
  const storedWorkspaceId = localStorage.getItem(WORKSPACE_STORAGE_KEY)
  const headers = AxiosHeaders.from(config.headers)

  if (storedSession?.accessToken) {
    headers.set('Authorization', `Bearer ${storedSession.accessToken}`)
  }

  if (storedWorkspaceId && !headers.get('X-Workspace-Id')) {
    headers.set('X-Workspace-Id', storedWorkspaceId)
  }

  config.headers = headers
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorEnvelope>) => {
    const errorPayload = error.response?.data?.error
    if (errorPayload?.code && errorPayload?.message) {
      throw new ApiError(
        errorPayload.code,
        errorPayload.message,
        error.response?.status,
        errorPayload.details
      )
    }

    throw new ApiError(
      'HTTP_ERROR',
      error.message || '网络请求失败，请稍后重试。',
      error.response?.status
    )
  }
)

export async function requestData<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await http.request<ApiEnvelope<T>>(config)
  return response.data.data
}

export async function requestVoid(config: AxiosRequestConfig): Promise<void> {
  await http.request({
    ...config,
    responseType: 'text'
  })
}

export async function requestPage<T>(
  config: AxiosRequestConfig
): Promise<PaginatedEnvelope<T>> {
  const response = await http.request<PaginatedEnvelope<T>>(config)
  return response.data
}
