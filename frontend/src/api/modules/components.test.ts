import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getComponentDetail,
  getComponentSteps
} from '@/api/modules/components'

const client = vi.hoisted(() => ({
  requestData: vi.fn(),
  requestPage: vi.fn(),
  requestVoid: vi.fn()
}))

vi.mock('@/api/client', () => client)

beforeEach((): void => {
  client.requestData.mockReset()
  client.requestPage.mockReset()
  client.requestVoid.mockReset()
})

describe('component preview APIs', (): void => {
  it('loads and maps component metadata for a case canvas preview', async (): Promise<void> => {
    client.requestData.mockResolvedValue({
      id: 42,
      workspace_id: 5,
      component_code: 'login',
      component_name: '登录组件',
      status: 'draft',
      description: '共享登录流程',
      published_at: null,
      created_at: '2026-08-15T00:00:00Z',
      updated_at: '2026-08-15T00:00:00Z'
    })

    await expect(getComponentDetail(42)).resolves.toMatchObject({
      id: 42,
      workspaceId: 5,
      name: '登录组件',
      status: 'draft'
    })
    expect(client.requestData).toHaveBeenCalledWith({
      method: 'get',
      url: '/components/42'
    })
  })

  it('loads ordered component steps with summaries for read-only projection', async (): Promise<void> => {
    client.requestData.mockResolvedValue([
      {
        id: 501,
        step_no: 1,
        step_type: 'input',
        step_name: '输入账号',
        template_id: null,
        component_id: null,
        payload_json: {
          selector: '#username',
          text: 'tester'
        },
        timeout_ms: 5000,
        retry_times: 1
      }
    ])

    await expect(getComponentSteps(42)).resolves.toEqual([
      expect.objectContaining({
        id: 501,
        stepNo: 1,
        name: '输入账号',
        type: 'input',
        target: '输入到 #username',
        timeoutMs: 5000,
        retryTimes: 1
      })
    ])
    expect(client.requestData).toHaveBeenCalledWith({
      method: 'get',
      url: '/components/42/steps'
    })
  })
})
