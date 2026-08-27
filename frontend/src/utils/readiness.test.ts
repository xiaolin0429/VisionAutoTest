import { describe, expect, it } from 'vitest'

import {
  buildReadinessNavigation,
  readinessIssuesFromErrorDetails,
  type ExecutionGateState
} from './readiness'

describe('execution readiness utilities', (): void => {
  it('keeps the six frozen gate states explicit', (): void => {
    const states: ExecutionGateState[] = [
      'idle',
      'checking',
      'blocked',
      'ready',
      'submitting',
      'check_failed'
    ]
    expect(states).toHaveLength(6)
  })

  it('maps backend 422 details without parsing error text', (): void => {
    expect(readinessIssuesFromErrorDetails([{
      code: 'ENVIRONMENT_BASE_URL_INVALID',
      message: '执行环境地址无效',
      resource_type: 'environment_profile',
      resource_id: 3,
      resource_name: '预发环境',
      route_path: '/environments',
      step_no: null
    }])).toEqual([{
      code: 'ENVIRONMENT_BASE_URL_INVALID',
      message: '执行环境地址无效',
      resourceType: 'environment_profile',
      resourceId: 3,
      resourceName: '预发环境',
      routePath: '/environments',
      stepNo: null
    }])
  })

  it('builds a resource-focused route for readiness repair', (): void => {
    expect(buildReadinessNavigation({
      code: 'DEVICE_PROFILE_INVALID',
      message: '设备不可用',
      resourceType: 'device_profile',
      resourceId: 9,
      resourceName: '笔记本',
      routePath: '/environments',
      stepNo: null
    })).toEqual({
      path: '/environments',
      query: { deviceProfileId: '9', stepNo: undefined }
    })
  })
})
