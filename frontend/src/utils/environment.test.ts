import { describe, expect, it } from 'vitest'

import { isValidEnvironmentBaseUrl } from './environment'

describe('environment base url validation', (): void => {
  it.each([
    'https://example.com',
    'http://localhost:5173/path',
    'http://127.0.0.1:8000',
    'http://[::1]:8000/path'
  ])('accepts absolute http(s) URL %s', (value: string): void => {
    expect(isValidEnvironmentBaseUrl(value)).toBe(true)
  })

  it.each(['www.feishu.cn', 'ftp://example.com', '/relative', 'https://', '']) (
    'rejects invalid URL %s',
    (value: string): void => {
      expect(isValidEnvironmentBaseUrl(value)).toBe(false)
    }
  )
})
