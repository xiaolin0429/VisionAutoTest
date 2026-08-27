import { describe, expect, it } from 'vitest'

import { formatPercent, formatRatio, formatStatusLabel } from './format'

describe('format utilities', (): void => {
  it.each<[string, string]>([
    ['active', '启用'],
    ['partial_failed', '部分失败'],
    ['custom', 'custom']
  ])('formats status "%s" as "%s"', (status: string, expected: string): void => {
    expect(formatStatusLabel(status)).toBe(expected)
  })

  it.each<[number, string]>([
    [0, '0%'],
    [0.456, '46%'],
    [1, '100%']
  ])('formats ratio %s as "%s"', (ratio: number, expected: string): void => {
    expect(formatRatio(ratio)).toBe(expected)
  })

  it('renders an unavailable percentage as --', (): void => {
    expect(formatPercent(null)).toBe('--')
    expect(formatPercent(29)).toBe('29%')
  })
})
