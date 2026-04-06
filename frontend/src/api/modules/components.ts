import { requestData, requestPage, requestVoid } from '@/api/client'
import type { ComponentReadDTO, TestCaseStepDTO } from '@/types/backend'
import type { Component, Step, StepType, StepWritePayload } from '@/types/models'
import { formatStepSummary } from '@/utils/steps'

function mapComponent(item: ComponentReadDTO): Component {
  // @param item Backend component summary DTO.
  // @returns Frontend component model used by list/detail views.
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
  // @param item Backend step DTO reused by component-step endpoints.
  // @returns Frontend step model enriched with summary text for table rendering.
  const summary = formatStepSummary({
    type: item.step_type as StepType,
    payloadJson: item.payload_json,
    templateId: item.template_id,
    componentId: item.component_id,
    timeoutMs: item.timeout_ms,
    retryTimes: item.retry_times
  })

  return {
    id: item.id,
    stepNo: item.step_no,
    name: item.step_name,
    type: item.step_type as StepType,
    templateId: item.template_id,
    componentId: item.component_id,
    target: summary.target,
    note: summary.note,
    payloadJson: item.payload_json,
    timeoutMs: item.timeout_ms,
    retryTimes: item.retry_times
  }
}

export async function listComponents(options?: { keyword?: string; status?: string }): Promise<Component[]> {
  // @param options Optional keyword/status filters for the component list page.
  const response = await requestPage<ComponentReadDTO>({
    method: 'get',
    url: '/components',
    params: {
      page: 1,
      page_size: 100,
      ...options
    }
  })

  return response.data.map(mapComponent)
}

export async function createComponent(payload: {
  code: string
  name: string
  description?: string
}): Promise<Component> {
  // @param payload Frontend create payload for a component.
  const response = await requestData<ComponentReadDTO>({
    method: 'post',
    url: '/components',
    data: {
      component_code: payload.code,
      component_name: payload.name,
      description: payload.description
    }
  })

  return mapComponent(response)
}

export async function getComponentDetail(componentId: number): Promise<Component> {
  // @param componentId Component id whose summary should be loaded.
  const response = await requestData<ComponentReadDTO>({
    method: 'get',
    url: `/components/${componentId}`
  })

  return mapComponent(response)
}

export async function updateComponent(
  componentId: number,
  payload: { name?: string; description?: string; status?: string }
): Promise<void> {
  // @param componentId Component id being updated.
  // @param payload Frontend update payload.
  await requestVoid({
    method: 'patch',
    url: `/components/${componentId}`,
    data: {
      component_name: payload.name,
      description: payload.description,
      status: payload.status
    }
  })
}

export async function getComponentSteps(componentId: number): Promise<Step[]> {
  // @param componentId Component id whose ordered steps should be loaded.
  const response = await requestData<TestCaseStepDTO[]>({
    method: 'get',
    url: `/components/${componentId}/steps`
  })

  return response.map(mapStep)
}

export async function replaceComponentSteps(
  componentId: number,
  steps: StepWritePayload[]
): Promise<void> {
  // @param componentId Component id whose steps should be fully replaced.
  // @param steps Ordered frontend step payload list.
  await requestVoid({
    method: 'put',
    url: `/components/${componentId}/steps`,
    data: {
      steps: steps.map((step) => ({
        step_no: step.stepNo,
        step_type: step.type,
        step_name: step.name,
        template_id: step.templateId,
        component_id: step.componentId,
        payload_json: step.payloadJson,
        timeout_ms: step.timeoutMs,
        retry_times: step.retryTimes
      }))
    }
  })
}
