import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { AppErrorPayload } from '@/types/errors'

export const useAppErrorStore = defineStore('appError', () => {
  const currentError = ref<AppErrorPayload | null>(null)
  const lastFingerprint = ref('')
  const lastRaisedAt = ref(0)

  const hasError = computed(() => currentError.value !== null)

  function setError(payload: AppErrorPayload) {
    const fingerprint = `${payload.source}:${payload.title}:${payload.message}`
    const now = Date.now()

    if (lastFingerprint.value === fingerprint && now - lastRaisedAt.value < 1500) {
      return
    }

    currentError.value = payload
    lastFingerprint.value = fingerprint
    lastRaisedAt.value = now
  }

  function clearError() {
    currentError.value = null
  }

  return {
    currentError,
    hasError,
    setError,
    clearError
  }
})
