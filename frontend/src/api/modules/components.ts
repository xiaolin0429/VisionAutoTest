import { requestPage } from '@/api/client'
import type { ComponentReadDTO } from '@/types/backend'
import type { Component } from '@/types/models'

function mapComponent(item: ComponentReadDTO): Component {
  return {
    id: item.id,
    workspaceId: item.workspace_id,
    code: item.component_code,
    name: item.component_name,
    status: item.status,
    description: item.description ?? '',
    publishedAt: item.published_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at
  }
}

export async function listComponents(): Promise<Component[]> {
  const response = await requestPage<ComponentReadDTO>({
    method: 'get',
    url: '/components',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return response.data.map(mapComponent)
}
