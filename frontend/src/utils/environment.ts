export const ENVIRONMENT_BASE_URL_MESSAGE =
  '请输入包含 http:// 或 https:// 的完整地址，例如 https://example.com'

export function isValidEnvironmentBaseUrl(value: string): boolean {
  const normalized = value.trim()
  if (!normalized) return false

  try {
    const url = new URL(normalized)
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname)
  } catch {
    return false
  }
}
