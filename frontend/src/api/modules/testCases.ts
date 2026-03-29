import { requestData, requestPage } from '@/api/client'
import type { TestCaseReadDTO, TestCaseStepDTO } from '@/types/backend'
import type {
  StepType,
  StepWritePayload,
  TestCase,
  TestCaseCreatePayload,
  TestCaseUpdatePayload
} from '@/types/models'

function formatTextValue(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) {
    return '--'
  }

  return value.trim()
}

function formatExtraPayloadKeys(
  payload: Record<string, unknown>,
  knownKeys: string[]
) {
  const extraKeys = Object.keys(payload).filter((key) => !knownKeys.includes(key))
  if (extraKeys.length === 0) {
    return ''
  }

  return ` · 扩展字段 ${extraKeys.join(', ')}`
}

function formatStepSummary(item: TestCaseStepDTO) {
  const payload = item.payload_json ?? {}
  const type = item.step_type as StepType
  const timeoutAndRetry = `超时 ${item.timeout_ms} ms · 重试 ${item.retry_times}`

  switch (type) {
    case 'wait': {
      const waitMs =
        typeof payload.ms === 'number' && Number.isFinite(payload.ms) ? payload.ms : '--'
      return {
        target: `等待 ${waitMs} ms`,
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['ms'])}`
      }
    }
    case 'click':
      return {
        target: `点击 ${formatTextValue(payload.selector)}`,
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['selector'])}`
      }
    case 'input':
      return {
        target: `输入到 ${formatTextValue(payload.selector)}`,
        note: `文本 ${formatTextValue(payload.text)} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          ['selector', 'text']
        )}`
      }
    case 'template_assert': {
      const threshold =
        typeof payload.threshold === 'number' && Number.isFinite(payload.threshold)
          ? `阈值 ${payload.threshold.toFixed(2)}`
          : '使用模板默认阈值'
      return {
        target: item.template_id ? `模板 #${item.template_id}` : '未选择模板',
        note: `${threshold} · ${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['threshold'])}`
      }
    }
    case 'ocr_assert': {
      const matchMode = payload.match_mode === 'exact' ? 'exact' : 'contains'
      const caseSensitive = payload.case_sensitive === true ? '区分大小写' : '忽略大小写'
      return {
        target: `OCR ${formatTextValue(payload.selector)}`,
        note: `期望文本 ${formatTextValue(payload.expected_text)} · ${matchMode} · ${caseSensitive} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          ['selector', 'expected_text', 'match_mode', 'case_sensitive']
        )}`
      }
    }
    case 'component_call':
      return {
        target: item.component_id ? `组件 #${item.component_id}` : '未选择组件',
        note: timeoutAndRetry
      }
    default:
      return {
        target: item.component_id
          ? `组件 #${item.component_id}`
          : item.template_id
            ? `模板 #${item.template_id}`
            : '--',
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, [])}`
      }
  }
}

function mapStep(item: TestCaseStepDTO) {
  const summary = formatStepSummary(item)

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

export async function createTestCase(payload: TestCaseCreatePayload): Promise<TestCase> {
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

export async function replaceTestCaseSteps(
  testCaseId: number,
  steps: StepWritePayload[]
): Promise<TestCase['steps']> {
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
