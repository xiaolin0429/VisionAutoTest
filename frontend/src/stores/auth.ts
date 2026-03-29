import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { StorageSerializers, useStorage } from '@vueuse/core'
import {
  AUTH_SESSION_STORAGE_KEY,
  AUTH_USER_STORAGE_KEY,
  WORKSPACE_STORAGE_KEY
} from '@/constants/storage'
import { ApiError } from '@/api/shared'
import { getCurrentSession, refreshSession } from '@/api/modules/auth'
import { pinia } from '@/stores/pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import type {
  CurrentSession,
  SessionCheckStatus,
  SessionPayload,
  SessionRefreshPayload,
  User
} from '@/types/models'

interface StoredSession {
  sessionId: string
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
  issuedAt: number
}

const SESSION_REFRESH_BUFFER_MS = 60 * 1000
const SESSION_LIFECYCLE_MESSAGES: Record<string, string> = {
  REFRESH_TOKEN_EXPIRED: '当前会话已失效，需要重新登录。',
  REFRESH_TOKEN_REVOKED: '当前会话已失效，需要重新登录。',
  REFRESH_TOKEN_INVALID: '当前会话已失效，需要重新登录。',
  TOKEN_REVOKED: '当前会话已被吊销或不存在，需要重新登录。',
  SESSION_NOT_FOUND: '当前会话已被吊销或不存在，需要重新登录。'
}

export const useAuthStore = defineStore('auth', () => {
  const session = useStorage<StoredSession | null>(AUTH_SESSION_STORAGE_KEY, null, undefined, {
    serializer: StorageSerializers.object
  })
  const user = useStorage<User | null>(AUTH_USER_STORAGE_KEY, null, undefined, {
    serializer: StorageSerializers.object
  })
  const currentSession = ref<CurrentSession | null>(null)
  const sessionCheckStatus = ref<SessionCheckStatus>('idle')
  const refreshing = ref(false)

  let refreshPromise: Promise<StoredSession | null> | null = null
  let sessionValidationPromise: Promise<CurrentSession | null> | null = null
  let refreshTimer: number | null = null

  const isAuthenticated = computed(() => {
    return Boolean(session.value?.sessionId && session.value?.refreshToken)
  })
  const hasSession = computed(() => isAuthenticated.value)
  const accessToken = computed(() => session.value?.accessToken ?? '')
  const accessTokenExpiresAt = computed(() => {
    if (!session.value?.issuedAt) {
      return 0
    }

    return session.value.issuedAt + session.value.expiresIn * 1000
  })
  const isAccessTokenExpired = computed(() => {
    return accessTokenExpiresAt.value > 0 && accessTokenExpiresAt.value <= Date.now()
  })
  const isAccessTokenExpiringSoon = computed(() => {
    return (
      accessTokenExpiresAt.value > 0 &&
      accessTokenExpiresAt.value - Date.now() <= SESSION_REFRESH_BUFFER_MS
    )
  })

  function clearRefreshTimer() {
    if (refreshTimer === null) {
      return
    }

    window.clearTimeout(refreshTimer)
    refreshTimer = null
  }

  function handleScheduledRefreshFailure(error: unknown) {
    if (!(error instanceof ApiError) || !(error.code in SESSION_LIFECYCLE_MESSAGES)) {
      return
    }

    sessionStorage.setItem('vat-auth-notice', SESSION_LIFECYCLE_MESSAGES[error.code])
    clearSession()
    useWorkspaceStore(pinia).reset()
    localStorage.removeItem(AUTH_SESSION_STORAGE_KEY)
    localStorage.removeItem(AUTH_USER_STORAGE_KEY)
    localStorage.removeItem(WORKSPACE_STORAGE_KEY)

    if (window.location.pathname === '/login') {
      return
    }

    const redirectTarget = `${window.location.pathname}${window.location.search}${window.location.hash}`
    const searchParams = new URLSearchParams({
      redirect: redirectTarget
    })
    window.location.replace(`/login?${searchParams.toString()}`)
  }

  function scheduleRefresh() {
    clearRefreshTimer()

    if (!session.value?.refreshToken || accessTokenExpiresAt.value <= 0) {
      return
    }

    const dueIn = Math.max(accessTokenExpiresAt.value - Date.now() - SESSION_REFRESH_BUFFER_MS, 0)

    refreshTimer = window.setTimeout(() => {
      void ensureSessionAvailable({ forceRefresh: true }).catch((error) => {
        handleScheduledRefreshFailure(error)
      })
    }, dueIn)
  }

  function applySessionPayload(nextSession: StoredSession, nextUser: User) {
    session.value = nextSession
    user.value = nextUser
  }

  function setSession(payload: SessionPayload) {
    applySessionPayload(
      {
        sessionId: payload.sessionId,
        accessToken: payload.accessToken,
        refreshToken: payload.refreshToken,
        tokenType: payload.tokenType,
        expiresIn: payload.expiresIn,
        issuedAt: payload.issuedAt
      },
      payload.user
    )
    currentSession.value = null
    sessionCheckStatus.value = 'idle'
  }

  function updateSessionTokens(payload: SessionRefreshPayload) {
    if (!session.value || !user.value) {
      throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
    }

    applySessionPayload(
      {
        ...session.value,
        accessToken: payload.accessToken,
        refreshToken: payload.refreshToken,
        tokenType: payload.tokenType,
        expiresIn: payload.expiresIn,
        issuedAt: payload.issuedAt
      },
      user.value
    )

    if (currentSession.value) {
      currentSession.value = {
        ...currentSession.value,
        expiresAt: new Date(payload.issuedAt + payload.expiresIn * 1000).toISOString()
      }
    }
  }

  function markCurrentSession(payload: CurrentSession) {
    currentSession.value = payload
    sessionCheckStatus.value = 'valid'
    user.value = payload.user
  }

  async function ensureSessionAvailable(options: { forceRefresh?: boolean } = {}) {
    if (!session.value?.sessionId || !session.value.refreshToken) {
      throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
    }

    if (!options.forceRefresh && !isAccessTokenExpiringSoon.value && !isAccessTokenExpired.value) {
      return session.value
    }

    if (refreshPromise) {
      return refreshPromise
    }

    refreshPromise = (async () => {
      refreshing.value = true
      const activeSessionId = session.value?.sessionId

      if (!activeSessionId || !session.value?.refreshToken) {
        throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
      }

      try {
        const payload = await refreshSession(session.value.refreshToken)
        if (session.value?.sessionId !== activeSessionId) {
          return session.value
        }

        updateSessionTokens(payload)
        return session.value
      } finally {
        refreshing.value = false
        refreshPromise = null
      }
    })()

    return refreshPromise
  }

  async function validateCurrentSession() {
    if (!session.value?.accessToken) {
      throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
    }

    if (sessionValidationPromise) {
      return sessionValidationPromise
    }

    sessionValidationPromise = (async () => {
      sessionCheckStatus.value = 'checking'

      try {
        const payload = await getCurrentSession()
        if (session.value?.sessionId && payload.sessionId !== session.value.sessionId) {
          throw new ApiError('SESSION_NOT_FOUND', '当前会话不存在。')
        }

        markCurrentSession(payload)
        return payload
      } catch (error) {
        sessionCheckStatus.value = 'invalid'
        currentSession.value = null
        throw error
      } finally {
        sessionValidationPromise = null
      }
    })()

    return sessionValidationPromise
  }

  async function bootstrapStoredSession() {
    if (!hasSession.value) {
      return null
    }

    await ensureSessionAvailable()

    if (sessionCheckStatus.value === 'valid' && currentSession.value) {
      return currentSession.value
    }

    return validateCurrentSession()
  }

  function clearSession() {
    clearRefreshTimer()
    refreshPromise = null
    sessionValidationPromise = null
    refreshing.value = false
    session.value = null
    user.value = null
    currentSession.value = null
    sessionCheckStatus.value = 'idle'
  }

  watch(
    session,
    () => {
      scheduleRefresh()
    },
    {
      deep: true,
      immediate: true
    }
  )

  return {
    session,
    user,
    currentSession,
    sessionCheckStatus,
    refreshing,
    accessToken,
    accessTokenExpiresAt,
    hasSession,
    isAccessTokenExpired,
    isAccessTokenExpiringSoon,
    isAuthenticated,
    setSession,
    updateSessionTokens,
    markCurrentSession,
    ensureSessionAvailable,
    validateCurrentSession,
    bootstrapStoredSession,
    clearSession
  }
})
