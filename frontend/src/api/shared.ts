import axios, { type AxiosError } from 'axios'

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

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorEnvelope>
    const errorPayload = axiosError.response?.data?.error

    if (errorPayload?.code && errorPayload?.message) {
      return new ApiError(
        errorPayload.code,
        errorPayload.message,
        axiosError.response?.status,
        errorPayload.details
      )
    }

    return new ApiError(
      'HTTP_ERROR',
      axiosError.message || '网络请求失败，请稍后重试。',
      axiosError.response?.status
    )
  }

  if (error instanceof Error) {
    return new ApiError('HTTP_ERROR', error.message)
  }

  return new ApiError('HTTP_ERROR', '网络请求失败，请稍后重试。')
}
