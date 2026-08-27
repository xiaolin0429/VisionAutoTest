import { describe, expect, it } from 'vitest'

import {
  buildStructuredRepairTarget,
  getReportConclusion,
  getUserFailureSummary,
  resolveRunRepairTarget
} from './runFailures'

describe('run failure repair targets', (): void => {
  it('routes an environment attribution to the environment profile', (): void => {
    expect(buildStructuredRepairTarget({
      resourceType: 'environment_profile',
      resourceId: 3,
      resourceName: '预发环境',
      routePath: '/environments',
      stepNo: null
    })).toMatchObject({
      kind: 'navigate',
      path: '/environments',
      query: { environmentProfileId: '3' },
      label: '去修复环境'
    })
  })

  it('keeps system failures out of business-resource routes', (): void => {
    expect(buildStructuredRepairTarget({
      resourceType: 'system',
      resourceId: null,
      resourceName: '平台运行环境',
      routePath: null,
      stepNo: null
    })).toEqual({
      kind: 'system',
      path: null,
      query: {},
      label: '重试执行',
      resourceName: '平台运行环境'
    })
  })

  it('falls back to system when old data has no structured repair metadata', (): void => {
    const target = resolveRunRepairTarget({
      id: 1,
      testRunId: 1,
      testSuiteId: 1,
      environmentProfileId: 1,
      deviceProfileId: null,
      suiteName: '回归套件',
      environmentName: '测试环境',
      deviceName: '默认设备',
      status: 'error',
      createdAt: '',
      startedAt: null,
      finishedAt: null,
      summary: { totalCases: 1, passedCases: 0, failedCases: 0, errorCases: 1, durationSeconds: 0 },
      caseRuns: []
    }, null)

    expect(target.kind).toBe('system')
    expect(target.path).toBeNull()
  })

  it('maps stable error codes to a user-facing summary', (): void => {
    expect(getUserFailureSummary({
      code: 'ENVIRONMENT_BASE_URL_INVALID',
      summary: 'Page.goto invalid URL'
    })).toContain('执行环境地址无效')
  })

  it('keeps a cancelled report conclusion in business-facing Chinese', (): void => {
    const conclusion = getReportConclusion('cancelled', {
      code: 'TEST_RUN_CANCELLED',
      summary: 'Test run was cancelled.'
    })

    expect(conclusion).toBe('本次执行已取消，已完成的用例结果已保留')
    expect(conclusion).not.toContain('Test run was cancelled.')
  })

  it('uses cancelled status instead of an unstructured raw summary', (): void => {
    expect(getReportConclusion('cancelled', {
      code: null,
      summary: 'Test run was cancelled.'
    })).toBe('本次执行已取消，已完成的用例结果已保留')
  })
})
