import { requestData, requestPage } from '@/api/client'
import type { ComponentReadDTO, TestCaseStepDTO } from '@/types/backend'
import type { Component, Step, StepType } from '@/types/models'

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

function mapStep(item: TestCaseStepDTO): Step {
  return {
    id: item.id,
    stepNo: item.step_no,
    name: item.step_name,
    type: item.step_type as StepType,
    templateId: item.template_id,
    componentId: item.component_id,
    target: '--',
    note: `超时 ${item.timeout_ms} ms · 重试 ${item.retry_times}`,
    payloadJson: item.payload_json,
    timeoutMs: item.timeout_ms,
    retryTimes: item.retry_times
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

export async function getComponentSteps(componentId: number): Promise<Step[]> {
  const response = await requestData<TestCaseStepDTO[]>({
    method: 'get',
    url: `/components/${componentId}/steps`
  })

  return response.map(mapStep)
}
