import { requestData, requestPage } from '@/api/client'
import type { TestCaseReadDTO, TestCaseStepDTO } from '@/types/backend'
import type {
  StepType,
  StepWritePayload,
  TestCase,
  TestCaseCreatePayload,
  TestCaseUpdatePayload
} from '@/types/models'
import { formatStepSummary } from '@/utils/steps'

function mapStep(item: TestCaseStepDTO) {
  // @param item Backend test-case-step DTO that still uses backend naming and payload structure.
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

function mapTestCaseSummary(item: TestCaseReadDTO): TestCase {
  // @param item Backend test-case summary DTO.
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

export async function listTestCases(options?: {
  keyword?: string
  status?: string
}): Promise<TestCase[]> {
  // @param options Optional keyword/status filters for the list page.
  const params: Record<string, string | number> = { page: 1, page_size: 100 }
  if (options?.keyword) {
    params.keyword = options.keyword
  }
  if (options?.status) {
    params.status = options.status
  }

  const response = await requestPage<TestCaseReadDTO>({
    method: 'get',
    url: '/test-cases',
    params
  })

  return response.data.map(mapTestCaseSummary)
}

export async function getTestCaseDetail(testCaseId: number): Promise<TestCase> {
  // @param testCaseId Test-case id whose summary and ordered steps should be aggregated.
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

export async function createTestCase(payload: TestCaseCreatePayload): Promise<TestCase> {
  // @param payload Frontend create payload using camelCase field names.
  const response = await requestData<TestCaseReadDTO>({
    method: 'post',
    url: '/test-cases',
    data: {
      case_code: payload.code,
      case_name: payload.name,
      status: payload.status,
      priority: payload.priority,
      description: payload.description
    }
  })

  return mapTestCaseSummary(response)
}

export async function updateTestCase(
  testCaseId: number,
  payload: TestCaseUpdatePayload
): Promise<TestCase> {
  // @param testCaseId Test-case id being updated.
  // @param payload Frontend update payload using camelCase field names.
  const response = await requestData<TestCaseReadDTO>({
    method: 'patch',
    url: `/test-cases/${testCaseId}`,
    data: {
      case_name: payload.name,
      status: payload.status,
      priority: payload.priority,
      description: payload.description
    }
  })

  return mapTestCaseSummary(response)
}

export async function cloneTestCase(testCaseId: number): Promise<TestCase> {
  // @param testCaseId Source test-case id to clone into a new draft copy.
  const response = await requestData<TestCaseReadDTO>({
    method: 'post',
    url: `/test-cases/${testCaseId}/clone`
  })

  return mapTestCaseSummary(response)
}

export async function replaceTestCaseSteps(
  testCaseId: number,
  steps: StepWritePayload[]
): Promise<TestCase['steps']> {
  // @param testCaseId Test-case id whose steps should be fully replaced.
  // @param steps Ordered frontend step payload list.
  const response = await requestData<TestCaseStepDTO[]>({
    method: 'put',
    url: `/test-cases/${testCaseId}/steps`,
    data: steps.map((item) => ({
      step_no: item.stepNo,
      step_type: item.type,
      step_name: item.name,
      template_id: item.templateId,
      component_id: item.componentId,
      payload_json: item.payloadJson,
      timeout_ms: item.timeoutMs,
      retry_times: item.retryTimes
    }))
  })

  return response.map(mapStep)
}
