import { AUTH_USER_STORAGE_KEY } from '@/constants/storage'
import { requestData, requestPage } from '@/api/client'
import type {
  ExecutionReadinessSummaryReadDTO,
  WorkspaceMemberReadDTO,
  WorkspaceReadDTO
} from '@/types/backend'
import type { ExecutionReadinessSummary, Workspace } from '@/types/models'

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
          item.owner_user_id === currentUserId
            ? 'workspace_admin'
            : currentMember?.workspace_role ?? 'workspace_member',
        createdAt: item.created_at,
        updatedAt: item.updated_at
      }
    })
  )
}

function mapExecutionReadiness(summary: ExecutionReadinessSummaryReadDTO): ExecutionReadinessSummary {
  return {
    scope: summary.scope,
    status: summary.status,
    workspaceId: summary.workspace_id,
    testSuiteId: summary.test_suite_id,
    activeEnvironmentCount: summary.active_environment_count,
    activeTestSuiteCount: summary.active_test_suite_count,
    blockingIssueCount: summary.blocking_issue_count,
    issues: summary.issues.map((issue) => ({
      code: issue.code,
      message: issue.message,
      resourceType: issue.resource_type,
      resourceId: issue.resource_id,
      resourceName: issue.resource_name ?? '',
      routePath: issue.route_path
    }))
  }
}

export async function getWorkspaceExecutionReadiness(
  workspaceId: number
): Promise<ExecutionReadinessSummary> {
  const response = await requestData<ExecutionReadinessSummaryReadDTO>({
    method: 'get',
    url: `/workspaces/${workspaceId}/execution-readiness`
  })

  return mapExecutionReadiness(response)
}
