import type { Router } from 'vue-router'
import { pinia } from '@/stores/pinia'
import { useAppErrorStore } from '@/stores/appError'
import type { AppErrorPayload } from '@/types/errors'

function normalizeUnknownError(error: unknown) {
  if (error instanceof Error) {
    return {
      title: error.name || '应用异常',
      message: error.message || '应用运行时发生未知异常。',
      detail: error.stack
    }
  }

  if (typeof error === 'string') {
    return {
      title: '应用异常',
      message: error,
      detail: undefined
    }
  }

  return {
    title: '应用异常',
    message: '应用运行时发生未知异常。',
    detail: safeSerialize(error)
  }
}

function safeSerialize(value: unknown) {
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function createAppErrorPayload(
  error: unknown,
  source: AppErrorPayload['source']
): AppErrorPayload {
  const normalized = normalizeUnknownError(error)

  return {
    id: `err_${Date.now()}`,
    title: normalized.title,
    message: normalized.message,
    detail: normalized.detail,
    source,
    timestamp: new Date().toISOString()
  }
}

export async function reportAppError(
  router: Router,
  error: unknown,
  source: AppErrorPayload['source']
) {
  const errorStore = useAppErrorStore(pinia)
  errorStore.setError(createAppErrorPayload(error, source))

  if (router.currentRoute.value.name !== 'error-state') {
    await router.push('/error')
  }
}
