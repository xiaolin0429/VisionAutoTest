import { computed } from 'vue'
import { defineStore } from 'pinia'
import { StorageSerializers, useStorage } from '@vueuse/core'
import {
  AUTH_SESSION_STORAGE_KEY,
  AUTH_USER_STORAGE_KEY
} from '@/constants/storage'
import type { SessionPayload, User } from '@/types/models'

interface StoredSession {
  sessionId: string
  accessToken: string
  refreshToken: string
  expiresIn: number
  issuedAt: number
}

export const useAuthStore = defineStore('auth', () => {
  const session = useStorage<StoredSession | null>(AUTH_SESSION_STORAGE_KEY, null, undefined, {
    serializer: StorageSerializers.object
  })
  const user = useStorage<User | null>(AUTH_USER_STORAGE_KEY, null, undefined, {
    serializer: StorageSerializers.object
  })

  const isAuthenticated = computed(() => {
    if (!session.value?.accessToken || !session.value.issuedAt) {
      return false
    }

    return session.value.issuedAt + session.value.expiresIn * 1000 > Date.now()
  })
  const accessToken = computed(() => session.value?.accessToken ?? '')

  function setSession(payload: SessionPayload) {
    session.value = {
      sessionId: payload.sessionId,
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken,
      expiresIn: payload.expiresIn,
      issuedAt: payload.issuedAt
    }
    user.value = payload.user
  }

  function clearSession() {
    session.value = null
    user.value = null
  }

  return {
    session,
    user,
    accessToken,
    isAuthenticated,
    setSession,
    clearSession
  }
})
