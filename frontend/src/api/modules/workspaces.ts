import { AUTH_USER_STORAGE_KEY } from '@/constants/storage'
import { requestData, requestPage } from '@/api/client'
import type {
  WorkspaceMemberReadDTO,
  WorkspaceReadDTO
} from '@/types/backend'
import type { Workspace } from '@/types/models'

function getStoredUserId() {
  const raw = localStorage.getItem(AUTH_USER_STORAGE_KEY)
  if (!raw) {
    return null
  }

  const user = JSON.parse(raw) as { id?: number }
  return typeof user.id === 'number' ? user.id : null
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const currentUserId = getStoredUserId()
  const response = await requestPage<WorkspaceReadDTO>({
    method: 'get',
    url: '/workspaces',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return Promise.all(
    response.data.map(async (item) => {
      const members = await requestData<WorkspaceMemberReadDTO[]>({
        method: 'get',
        url: `/workspaces/${item.id}/members`
      })
      const currentMember = members.find((member) => member.user_id === currentUserId)

      return {
        id: item.id,
        ownerUserId: item.owner_user_id,
        name: item.workspace_name,
        code: item.workspace_code,
        description: item.description ?? '',
        status: item.status,
        memberCount: members.length,
        role:
          currentMember?.workspace_role ??
          (item.owner_user_id === currentUserId ? 'workspace_admin' : 'workspace_member'),
        createdAt: item.created_at,
        updatedAt: item.updated_at
      }
    })
  )
}
