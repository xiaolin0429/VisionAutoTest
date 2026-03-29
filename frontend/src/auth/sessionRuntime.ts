import { AUTH_SESSION_STORAGE_KEY } from '@/constants/storage'
import { pinia } from '@/stores/pinia'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { ApiError } from '@/api/shared'

const AUTH_NOTICE_STORAGE_KEY = 'vat-auth-notice'

const sessionFailureMessageMap: Record<string, string> = {
  REFRESH_TOKEN_EXPIRED: '当前会话已失效，需要重新登录。',
  REFRESH_TOKEN_REVOKED: '当前会话已失效，需要重新登录。',
  REFRESH_TOKEN_INVALID: '当前会话已失效，需要重新登录。',
  TOKEN_REVOKED: '当前会话已被吊销或不存在，需要重新登录。',
  SESSION_NOT_FOUND: '当前会话已被吊销或不存在，需要重新登录。'
}

export function hasStoredSession() {
  return Boolean(localStorage.getItem(AUTH_SESSION_STORAGE_KEY))
}

export function resetClientSessionState() {
  useAuthStore(pinia).clearSession()
  useWorkspaceStore(pinia).reset()
}

export function queueAuthNotice(message: string) {
  sessionStorage.setItem(AUTH_NOTICE_STORAGE_KEY, message)
}

export function consumeAuthNotice() {
  const message = sessionStorage.getItem(AUTH_NOTICE_STORAGE_KEY)
  if (!message) {
    return null
  }

  sessionStorage.removeItem(AUTH_NOTICE_STORAGE_KEY)
  return message
}

export function isSessionLifecycleError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code in sessionFailureMessageMap
}

export function resolveSessionLifecycleMessage(error: unknown) {
  if (error instanceof ApiError && error.code in sessionFailureMessageMap) {
    return sessionFailureMessageMap[error.code]
  }

  return '当前会话校验失败，需要重新登录。'
}

export function buildLoginLocation(redirectPath?: string) {
  if (!redirectPath || redirectPath === '/login') {
    return '/login'
  }

  const searchParams = new URLSearchParams({
    redirect: redirectPath
  })
  return `/login?${searchParams.toString()}`
}

export function redirectToLogin(options: { redirectPath?: string; message?: string } = {}) {
  if (options.message) {
    queueAuthNotice(options.message)
  }

  const target = buildLoginLocation(options.redirectPath)

  if (window.location.pathname === '/login') {
    return
  }

  window.location.replace(target)
}
