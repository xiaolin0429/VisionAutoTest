import { requestData, requestPage } from '@/api/client'
import type { TestCaseReadDTO, TestCaseStepDTO } from '@/types/backend'
import type { TestCase } from '@/types/models'

function formatPayloadTarget(payload: Record<string, unknown>) {
  const keys = Object.keys(payload)
  if (keys.length === 0) {
    return '--'
  }

  return JSON.stringify(payload)
}

function mapStep(item: TestCaseStepDTO) {
  const target = item.component_id
    ? `组件 #${item.component_id}`
    : item.template_id
      ? `模板 #${item.template_id}`
      : formatPayloadTarget(item.payload_json)

  return {
    id: item.id,
    stepNo: item.step_no,
    name: item.step_name,
    type: item.step_type,
    templateId: item.template_id,
    componentId: item.component_id,
    target,
    note: `timeout ${item.timeout_ms} ms · retry ${item.retry_times}`,
    payloadJson: item.payload_json,
    timeoutMs: item.timeout_ms,
    retryTimes: item.retry_times
  }
}

function mapTestCaseSummary(item: TestCaseReadDTO): TestCase {
  return {
    id: item.id,
    code: item.case_code,
    name: item.case_name,
    status: item.status,
    priority: item.priority,
    description: item.description ?? '',
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    componentCount: 0,
    steps: []
  }
}

export async function listTestCases(): Promise<TestCase[]> {
  const response = await requestPage<TestCaseReadDTO>({
    method: 'get',
    url: '/test-cases',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return response.data.map(mapTestCaseSummary)
}

export async function getTestCaseDetail(testCaseId: number): Promise<TestCase> {
  const [testCase, steps] = await Promise.all([
    requestData<TestCaseReadDTO>({
      method: 'get',
      url: `/test-cases/${testCaseId}`
    }),
    requestData<TestCaseStepDTO[]>({
      method: 'get',
      url: `/test-cases/${testCaseId}/steps`
    })
  ])

  const mappedSteps = steps.map(mapStep)

  return {
    ...mapTestCaseSummary(testCase),
    componentCount: mappedSteps.filter((item) => item.componentId !== null).length,
    steps: mappedSteps
  }
}
