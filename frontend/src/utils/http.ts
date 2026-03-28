import { ApiError } from '@/api/client'

const postgresSetupHint =
  '请确认 PostgreSQL 已启动，已执行 `cd backend && python -m app.db.bootstrap`，并已启动后端服务。'

export function formatLinkupErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.statusCode && error.statusCode >= 500) {
      return `${error.message} ${postgresSetupHint}`
    }

    return error.message
  }

  if (error instanceof Error) {
    const normalizedMessage = error.message.toLowerCase()
    const needsSetupHint =
      normalizedMessage.includes('network error') ||
      normalizedMessage.includes('failed to fetch') ||
      normalizedMessage.includes('status code 500')

    if (needsSetupHint) {
      return `${error.message} ${postgresSetupHint}`
    }

    return error.message
  }

  return `${fallback} ${postgresSetupHint}`
}
