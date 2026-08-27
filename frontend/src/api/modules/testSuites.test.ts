import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getTestSuiteExecutionReadiness } from './testSuites'

const client = vi.hoisted(() => ({
  requestData: vi.fn(),
  requestPage: vi.fn()
}))

vi.mock('@/api/client', () => ({
  requestData: client.requestData,
  requestPage: client.requestPage
}))

beforeEach((): void => {
  client.requestData.mockReset()
  client.requestPage.mockReset()
})

describe('suite execution selection readiness', (): void => {
  it('sends the selected environment and optional device as query params', async (): Promise<void> => {
    client.requestData.mockResolvedValue({
      scope: 'execution_selection',
      status: 'ready',
      workspace_id: 1,
      test_suite_id: 2,
      environment_profile_id: 3,
      device_profile_id: 4,
      active_environment_count: 1,
      active_test_suite_count: 1,
      blocking_issue_count: 0,
      issues: []
    })

    const summary = await getTestSuiteExecutionReadiness(2, {
      environmentProfileId: 3,
      deviceProfileId: 4
    })

    expect(client.requestData).toHaveBeenCalledWith({
      method: 'get',
      url: '/test-suites/2/execution-readiness',
      params: {
        environment_profile_id: 3,
        device_profile_id: 4
      }
    })
    expect(summary).toMatchObject({
      scope: 'execution_selection',
      environmentProfileId: 3,
      deviceProfileId: 4
    })
  })
})
