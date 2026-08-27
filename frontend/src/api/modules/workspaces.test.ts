import { beforeEach, describe, expect, it, vi } from 'vitest'

import { listWorkspaces } from './workspaces'
import { AUTH_USER_STORAGE_KEY } from '@/constants/storage'

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
  localStorage.clear()
})

describe('workspace role mapping', (): void => {
  it('keeps the role unknown instead of guessing workspace_member', async (): Promise<void> => {
    localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify({ id: 9 }))
    client.requestPage.mockResolvedValue({
      data: [{
        id: 1,
        workspace_code: 'demo',
        workspace_name: '演示空间',
        description: null,
        status: 'active',
        owner_user_id: 2,
        created_at: '',
        updated_at: ''
      }]
    })
    client.requestData.mockResolvedValue([])

    const workspaces = await listWorkspaces()

    expect(workspaces[0]?.role).toBeNull()
  })

  it('resolves the owner role after workspace bootstrap data arrives', async (): Promise<void> => {
    localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify({ id: 2 }))
    client.requestPage.mockResolvedValue({
      data: [{
        id: 1,
        workspace_code: 'demo',
        workspace_name: '演示空间',
        description: null,
        status: 'active',
        owner_user_id: 2,
        created_at: '',
        updated_at: ''
      }]
    })
    client.requestData.mockResolvedValue([])

    const workspaces = await listWorkspaces()

    expect(workspaces[0]?.role).toBe('workspace_admin')
  })
})
