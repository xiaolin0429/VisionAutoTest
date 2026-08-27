import type {
  CaseRun,
  RepairResourceType,
  RepairTarget,
  ReportSummaryFailure,
  RunDetail,
  StepResult,
  TestRun
} from '@/types/models'
import { isAttentionRunStatus } from '@/utils/runMetrics'

export { isAttentionRunStatus }

export interface RunRepairTarget {
  kind: 'navigate' | 'system'
  path: string | null
  query: Record<string, string | undefined>
  label: string
  resourceName: string
}

const failureSummaryMap: Record<string, string> = {
  ENVIRONMENT_BASE_URL_INVALID: '执行环境地址无效，本次验证未能正常开始。',
  DEVICE_PROFILE_INVALID: '设备档案不可用于本次执行。',
  TEST_SUITE_EMPTY: '测试套件没有可执行用例。',
  TEST_SUITE_NOT_ACTIVE: '测试套件当前未激活。',
  PUBLISHED_VERSION_REQUIRED: '用例或公共组件尚未发布。',
  STEP_CONFIGURATION_INVALID: '步骤配置不完整，无法按预期执行。',
  BASELINE_REVISION_REQUIRED: '视觉模板缺少可执行的当前基准。',
  TEMPLATE_ASSERTION_FAILED: '页面画面与模板预期不一致。',
  OCR_ASSERTION_FAILED: '页面文字与断言预期不一致。',
  BROWSER_EXECUTION_ERROR: '浏览器执行异常，本次验证未正常完成。',
  SCREENSHOT_CAPTURE_FAILED: '截图生成异常，本次验证未正常完成。',
  TEST_RUN_EXECUTION_ERROR: '平台运行时异常，本次验证未正常完成。',
  TEST_RUN_CANCELLED: '本次执行已取消，已完成的用例结果已保留'
}

const reportConclusionByStatus: Record<string, string> = {
  queued: '本次执行正在排队，请稍候。',
  running: '本次执行正在进行，请稍候。',
  cancelling: '本次执行正在取消，已完成的用例结果将保留。',
  cancelled: '本次执行已取消，已完成的用例结果已保留',
  passed: '本次执行已通过，所有用例结果均符合预期。',
  failed: '本次执行存在未通过的用例，请查看失败证据并修复责任资源。',
  partial_failed: '本次执行部分用例未通过或异常，请优先处理需关注项。',
  error: '本次执行遇到异常，未能正常完成，请查看技术详情后重试。'
}

function repairQuery(
  resourceType: RepairResourceType,
  resourceId: number | null,
  stepNo: number | null
): Record<string, string | undefined> {
  if (resourceId === null) return {}

  const queryKeyMap: Partial<Record<RepairResourceType, string>> = {
    environment_profile: 'environmentProfileId',
    device_profile: 'deviceProfileId',
    test_suite: 'testSuiteId',
    test_case: 'testCaseId',
    component: 'componentId',
    template: 'templateId'
  }
  const key = queryKeyMap[resourceType]
  return key
    ? {
        [key]: String(resourceId),
        stepNo: stepNo === null ? undefined : String(stepNo),
        ...(resourceType === 'template' ? { focus: 'workbench' } : {})
      }
    : {}
}

function repairLabel(resourceType: RepairResourceType): string {
  const labelMap: Record<RepairResourceType, string> = {
    environment_profile: '去修复环境',
    device_profile: '去修复设备',
    test_suite: '去修复套件',
    test_case: '去修复测试用例',
    component: '去修复公共组件',
    template: '去修复模板',
    system: '重试执行'
  }
  return labelMap[resourceType]
}

export function buildStructuredRepairTarget(target: RepairTarget): RunRepairTarget {
  if (target.resourceType === 'system') {
    return {
      kind: 'system',
      path: null,
      query: {},
      label: '重试执行',
      resourceName: target.resourceName || '平台运行环境'
    }
  }

  return {
    kind: 'navigate',
    path: target.routePath,
    query: repairQuery(target.resourceType, target.resourceId, target.stepNo),
    label: repairLabel(target.resourceType),
    resourceName: target.resourceName
  }
}

export function buildResourceRepairTarget(step: StepResult | null): RunRepairTarget {
  if (!step?.repairResourceType || step.repairResourceType === 'system') {
    return buildStructuredRepairTarget({
      resourceType: 'system',
      resourceId: null,
      resourceName: '平台运行环境',
      routePath: null,
      stepNo: null
    })
  }

  return buildStructuredRepairTarget({
    resourceType: step.repairResourceType,
    resourceId: step.repairResourceId,
    resourceName: '',
    routePath: step.repairRoutePath,
    stepNo: step.repairStepNo
  })
}

export function getPrimaryRepairStep(caseRun: CaseRun | null): StepResult | null {
  if (!caseRun) return null
  return caseRun.steps.find((item) => item.status === 'failed' || item.status === 'error') ?? null
}

export function getPrimaryFailedCaseRun(detail: RunDetail | null): CaseRun | null {
  if (!detail) return null
  return detail.caseRuns.find((item) => item.status === 'failed' || item.status === 'error') ?? null
}

export function resolveRunRepairTarget(
  detail: RunDetail | null,
  failure?: ReportSummaryFailure | null
) {
  const failedCaseRun = getPrimaryFailedCaseRun(detail)
  const repairTarget = failure?.repairTarget
    ? buildStructuredRepairTarget(failure.repairTarget)
    : buildResourceRepairTarget(getPrimaryRepairStep(failedCaseRun))

  return {
    ...repairTarget,
    caseRunName: failedCaseRun?.name ?? '执行批次',
    failureSummary: getUserFailureSummary(failure, failedCaseRun?.failureSummary)
  }
}

export function getUserFailureSummary(
  failure?: Pick<ReportSummaryFailure, 'code' | 'summary'> | null,
  _fallback?: string | null
): string {
  if (failure?.code && failureSummaryMap[failure.code]) {
    return failureSummaryMap[failure.code]
  }
  if (!failure?.code && failure?.summary) return failure.summary
  return '本次验证未正常完成，请查看技术详情后重试。'
}

export function getReportConclusion(
  status: string,
  failure?: Pick<ReportSummaryFailure, 'code' | 'summary'> | null
): string {
  if (status === 'cancelled') {
    return reportConclusionByStatus.cancelled
  }
  if (failure?.code && failureSummaryMap[failure.code]) {
    return failureSummaryMap[failure.code]
  }
  return reportConclusionByStatus[status] ?? '本次执行已完成。'
}

export function getRunFailureSuggestion(run: TestRun) {
  if (run.status === 'failed') {
    return '存在断言未通过，请查看证据并定位责任资源。'
  }
  if (run.status === 'partial_failed') {
    return '部分用例未通过或异常，请优先处理第一个需关注项。'
  }
  if (run.status === 'error') {
    return '本次验证未正常完成，请查看异常归因与技术详情。'
  }
  return '当前执行状态无需额外修复动作。'
}
