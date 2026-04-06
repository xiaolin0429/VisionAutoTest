import axios, { AxiosHeaders, type AxiosRequestConfig } from 'axios'
import {
  AUTH_SESSION_STORAGE_KEY,
  AUTH_USER_STORAGE_KEY,
  WORKSPACE_STORAGE_KEY
} from '@/constants/storage'
import type { ApiEnvelope, PaginatedEnvelope } from '@/types/backend'
import { pinia } from '@/stores/pinia'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import {
  redirectToLogin as redirectToLoginPage,
  resetClientSessionState,
  resolveSessionLifecycleMessage
} from '@/auth/sessionRuntime'
import { API_BASE_URL, ApiError, toApiError } from '@/api/shared'

interface RetriableAxiosRequestConfig extends AxiosRequestConfig {
  _vatRetried?: boolean
}

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000
})

export { ApiError }

export function clearPersistedAuthState() {
  // Clears all persisted client-side auth/workspace state.
  // This is used when session lifecycle recovery is no longer possible in place.
  localStorage.removeItem(AUTH_SESSION_STORAGE_KEY)
  localStorage.removeItem(AUTH_USER_STORAGE_KEY)
  localStorage.removeItem(WORKSPACE_STORAGE_KEY)
}

function shouldSkipAutoRefresh(requestUrl: string) {
  // @param requestUrl Request URL used to identify lifecycle endpoints.
  // @returns True when the global 401 refresh flow must not retry this request.
  // Session creation/inspection/refresh endpoints are the lifecycle source of truth.
  // Retrying them through the global 401 refresh flow would recurse into the same boundary.
  return (
    requestUrl.endsWith('/sessions') ||
    requestUrl.endsWith('/sessions/current') ||
    requestUrl.endsWith('/session-refreshes')
  )
}

function redirectToLoginWithNotice(message?: string) {
  // @param message Optional notice shown after redirect when the session has expired or been revoked.
  const redirectTarget = `${window.location.pathname}${window.location.search}${window.location.hash}`
  redirectToLoginPage({
    redirectPath: redirectTarget,
    message
  })
}

http.interceptors.request.use((config) => {
  const authStore = useAuthStore(pinia)
  const workspaceStore = useWorkspaceStore(pinia)
  const storedWorkspaceId = workspaceStore.currentWorkspaceId !== null
    ? String(workspaceStore.currentWorkspaceId)
    : localStorage.getItem(WORKSPACE_STORAGE_KEY)
  const headers = AxiosHeaders.from(config.headers)

  // Authorization and workspace scope are injected centrally so feature modules stay
  // resource-oriented instead of re-implementing cross-cutting request context.
  if (authStore.session?.accessToken) {
    headers.set(
      'Authorization',
      `${authStore.session.tokenType ?? 'Bearer'} ${authStore.session.accessToken}`
    )
  }

  if (storedWorkspaceId && !headers.get('X-Workspace-Id')) {
    headers.set('X-Workspace-Id', storedWorkspaceId)
  }

  config.headers = headers
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = String(error.config?.url ?? '')
    const requestConfig = error.config as RetriableAxiosRequestConfig | undefined
    const authStore = useAuthStore(pinia)
    const apiError = toApiError(error)
    const shouldAttemptRefresh =
      apiError.statusCode === 401 &&
      authStore.hasSession &&
      requestConfig !== undefined &&
      !requestConfig._vatRetried &&
      !shouldSkipAutoRefresh(requestUrl)

    // A protected request gets exactly one silent refresh + replay attempt.
    // The retried flag prevents loops when the new token is also rejected.
    if (shouldAttemptRefresh) {
      try {
        await authStore.ensureSessionAvailable({ forceRefresh: true })
        if (!authStore.session?.accessToken) {
          throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
        }

        requestConfig._vatRetried = true
        const retryHeaders = AxiosHeaders.from(
          requestConfig.headers ? (requestConfig.headers as AxiosHeaders) : {}
        )
        retryHeaders.set(
          'Authorization',
          `${authStore.session.tokenType ?? 'Bearer'} ${authStore.session.accessToken}`
        )
        requestConfig.headers = retryHeaders

        return http.request(requestConfig)
      } catch (refreshError) {
        const normalizedRefreshError = toApiError(refreshError)
        if (
          ['REFRESH_TOKEN_EXPIRED', 'REFRESH_TOKEN_REVOKED', 'REFRESH_TOKEN_INVALID', 'TOKEN_REVOKED', 'SESSION_NOT_FOUND'].includes(
            normalizedRefreshError.code
          )
        ) {
          // Lifecycle failures mean the client can no longer recover in place.
          // Clear both auth and workspace context before sending the user back to login.
          resetClientSessionState()
          clearPersistedAuthState()
          redirectToLoginWithNotice(resolveSessionLifecycleMessage(normalizedRefreshError))
        }

        throw normalizedRefreshError
      }
    }

    throw apiError
  }
)

export async function requestData<T>(config: AxiosRequestConfig): Promise<T> {
  // @param config Axios request config for an API endpoint that returns the standard data envelope.
  // @returns The unwrapped `data` payload so callers stay focused on domain models.
  const response = await http.request<ApiEnvelope<T>>(config)
  return response.data.data
}

export async function requestVoid(config: AxiosRequestConfig): Promise<void> {
  // @param config Axios request config for endpoints whose success does not expose a typed payload.
  await http.request({
    ...config,
    responseType: 'text'
  })
}

export async function requestBlob(config: AxiosRequestConfig): Promise<Blob> {
  // @param config Axios request config for binary/media endpoints.
  // @returns The raw blob body returned by the server.
  const response = await http.request<Blob>({
    ...config,
    responseType: 'blob'
  })
  return response.data
}

export async function requestPage<T>(
  config: AxiosRequestConfig
): Promise<PaginatedEnvelope<T>> {
  // @param config Axios request config for list endpoints using the shared paginated envelope.
  // @returns The full paginated response so callers can access items and pagination metadata.
  const response = await http.request<PaginatedEnvelope<T>>(config)
  return response.data
}
