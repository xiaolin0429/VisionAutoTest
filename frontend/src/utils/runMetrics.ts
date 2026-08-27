import type { TestRun } from '@/types/models'

export const ATTENTION_RUN_STATUSES = ['failed', 'partial_failed', 'error'] as const
export const EFFECTIVE_TERMINAL_RUN_STATUSES = [
  'passed',
  'failed',
  'partial_failed',
  'error'
] as const

const attentionStatusSet = new Set<string>(ATTENTION_RUN_STATUSES)
const effectiveTerminalStatusSet = new Set<string>(EFFECTIVE_TERMINAL_RUN_STATUSES)

export interface RunMetrics {
  total: number
  passed: number
  failed: number
  partialFailed: number
  error: number
  cancelled: number
  attention: number
  effectiveTerminal: number
  passRate: number | null
}

export interface CaseResultDistributionItem {
  key: 'passed' | 'failed' | 'error'
  label: '通过' | '失败' | '异常'
  count: number
}

export function isAttentionRunStatus(status: string): boolean {
  return attentionStatusSet.has(status)
}

export function calculateRunMetrics(runs: Pick<TestRun, 'status'>[]): RunMetrics {
  const counts = {
    passed: 0,
    failed: 0,
    partialFailed: 0,
    error: 0,
    cancelled: 0
  }

  for (const run of runs) {
    if (run.status === 'passed') counts.passed += 1
    if (run.status === 'failed') counts.failed += 1
    if (run.status === 'partial_failed') counts.partialFailed += 1
    if (run.status === 'error') counts.error += 1
    if (run.status === 'cancelled') counts.cancelled += 1
  }

  const effectiveTerminal = runs.filter((run) =>
    effectiveTerminalStatusSet.has(run.status)
  ).length
  const attention = counts.failed + counts.partialFailed + counts.error

  return {
    total: runs.length,
    ...counts,
    attention,
    effectiveTerminal,
    passRate:
      effectiveTerminal === 0
        ? null
        : Math.round((counts.passed / effectiveTerminal) * 100)
  }
}

export function calculateCasePassRate(
  counts: Pick<TestRun, 'passedCaseCount' | 'failedCaseCount' | 'errorCaseCount'>
): number | null {
  const effectiveTerminalCases =
    counts.passedCaseCount + counts.failedCaseCount + counts.errorCaseCount
  return effectiveTerminalCases === 0
    ? null
    : Math.round((counts.passedCaseCount / effectiveTerminalCases) * 100)
}

export function buildCaseResultDistribution(
  counts: Pick<TestRun, 'passedCaseCount' | 'failedCaseCount' | 'errorCaseCount'>
): CaseResultDistributionItem[] {
  return [
    { key: 'passed', label: '通过', count: counts.passedCaseCount },
    { key: 'failed', label: '失败', count: counts.failedCaseCount },
    { key: 'error', label: '异常', count: counts.errorCaseCount }
  ]
}

export function calculateAggregateCasePassRate(
  runs: Pick<TestRun, 'passedCaseCount' | 'failedCaseCount' | 'errorCaseCount'>[]
): number | null {
  return calculateCasePassRate(
    runs.reduce(
      (total, run) => ({
        passedCaseCount: total.passedCaseCount + run.passedCaseCount,
        failedCaseCount: total.failedCaseCount + run.failedCaseCount,
        errorCaseCount: total.errorCaseCount + run.errorCaseCount
      }),
      { passedCaseCount: 0, failedCaseCount: 0, errorCaseCount: 0 }
    )
  )
}
