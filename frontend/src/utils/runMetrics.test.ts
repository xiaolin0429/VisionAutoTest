import { describe, expect, it } from 'vitest'

import {
  buildCaseResultDistribution,
  calculateAggregateCasePassRate,
  calculateCasePassRate,
  calculateRunMetrics,
  isAttentionRunStatus
} from './runMetrics'

describe('run metrics', (): void => {
  it('counts every terminal status with the frozen attention and pass-rate rules', (): void => {
    const metrics = calculateRunMetrics([
      { status: 'passed' },
      { status: 'passed' },
      { status: 'failed' },
      { status: 'partial_failed' },
      { status: 'error' },
      { status: 'error' },
      { status: 'error' },
      { status: 'cancelled' },
      { status: 'running' }
    ])

    expect(metrics).toMatchObject({
      total: 9,
      passed: 2,
      failed: 1,
      partialFailed: 1,
      error: 3,
      cancelled: 1,
      attention: 5,
      effectiveTerminal: 7,
      passRate: 29
    })
  })

  it('returns null instead of 0 percent without effective terminal results', (): void => {
    expect(calculateRunMetrics([{ status: 'queued' }, { status: 'cancelled' }]).passRate)
      .toBeNull()
    expect(calculateCasePassRate({
      passedCaseCount: 0,
      failedCaseCount: 0,
      errorCaseCount: 0
    })).toBeNull()
  })

  it('uses only passed, failed and error cases in the case denominator', (): void => {
    expect(calculateCasePassRate({
      passedCaseCount: 2,
      failedCaseCount: 1,
      errorCaseCount: 1
    })).toBe(50)
    expect(calculateAggregateCasePassRate([
      { passedCaseCount: 1, failedCaseCount: 0, errorCaseCount: 0 },
      { passedCaseCount: 1, failedCaseCount: 1, errorCaseCount: 1 }
    ])).toBe(50)
  })

  it('builds a fixed passed, failed and error case distribution', (): void => {
    expect(buildCaseResultDistribution({
      passedCaseCount: 2,
      failedCaseCount: 3,
      errorCaseCount: 4
    })).toEqual([
      { key: 'passed', label: '通过', count: 2 },
      { key: 'failed', label: '失败', count: 3 },
      { key: 'error', label: '异常', count: 4 }
    ])
  })

  it('keeps all three case result categories when every count is zero', (): void => {
    expect(buildCaseResultDistribution({
      passedCaseCount: 0,
      failedCaseCount: 0,
      errorCaseCount: 0
    })).toEqual([
      { key: 'passed', label: '通过', count: 0 },
      { key: 'failed', label: '失败', count: 0 },
      { key: 'error', label: '异常', count: 0 }
    ])
  })

  it.each(['failed', 'partial_failed', 'error'])(
    'treats %s as attention',
    (status: string): void => {
      expect(isAttentionRunStatus(status)).toBe(true)
    }
  )
})
