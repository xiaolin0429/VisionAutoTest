import { ApiError, requestData, requestPage } from '@/api/client'
import type {
  DeviceProfileReadDTO,
  EnvironmentProfileReadDTO,
  ReportArtifactReadDTO,
  ReportSummaryDTO,
  RunReportReadDTO,
  StepResultReadDTO,
  TestCaseReadDTO,
  TestCaseRunReadDTO,
  TestRunReadDTO,
  TestSuiteReadDTO
} from '@/types/backend'
import type {
  ReportArtifact,
  ReportSummary,
  RunDetail,
  RunReport,
  TestRun
} from '@/types/models'

function createLookupMap<T extends { id: number }>(items: T[]) {
  return new Map(items.map((item) => [item.id, item]))
}

async function loadReferenceMaps() {
  const [suites, environments, devices, cases] = await Promise.all([
    requestPage<TestSuiteReadDTO>({
      method: 'get',
      url: '/test-suites',
      params: { page: 1, page_size: 100 }
    }),
    requestPage<EnvironmentProfileReadDTO>({
      method: 'get',
      url: '/environment-profiles',
      params: { page: 1, page_size: 100 }
    }),
    requestPage<DeviceProfileReadDTO>({
      method: 'get',
      url: '/device-profiles',
      params: { page: 1, page_size: 100 }
    }),
    requestPage<TestCaseReadDTO>({
      method: 'get',
      url: '/test-cases',
      params: { page: 1, page_size: 100 }
    })
  ])

  return {
    suiteMap: createLookupMap(suites.data),
    environmentMap: createLookupMap(environments.data),
    deviceMap: createLookupMap(devices.data),
    caseMap: createLookupMap(cases.data)
  }
}

function mapRun(
  item: TestRunReadDTO,
  reference: Awaited<ReturnType<typeof loadReferenceMaps>>
): TestRun {
  const suite = reference.suiteMap.get(item.test_suite_id)
  const environment = reference.environmentMap.get(item.environment_profile_id)
  const device = item.device_profile_id
    ? reference.deviceMap.get(item.device_profile_id)
    : null

  return {
    id: item.id,
    testSuiteId: item.test_suite_id,
    suiteName: suite?.suite_name ?? `套件 #${item.test_suite_id}`,
    environmentProfileId: item.environment_profile_id,
    environmentName: environment?.profile_name ?? `环境 #${item.environment_profile_id}`,
    deviceProfileId: item.device_profile_id,
    deviceName: device?.profile_name ?? '未指定设备',
    status: item.status,
    triggerSource: item.trigger_source,
    createdAt: item.created_at,
    startedAt: item.started_at,
    finishedAt: item.finished_at,
    totalCaseCount: item.total_case_count,
    passedCaseCount: item.passed_case_count,
    failedCaseCount: item.failed_case_count,
    errorCaseCount: item.error_case_count
  }
}

function mapStepResult(item: StepResultReadDTO) {
  const branchPrefix =
    item.parent_step_no !== null
      ? `分支 ${item.branch_name ?? item.branch_key ?? '未命名'} · `
      : ''
  return {
    id: item.id,
    stepNo: item.step_no,
    name: item.step_type
      ? `${branchPrefix}${item.step_type} · Step ${item.step_no}`
      : `${branchPrefix}Step ${item.step_no}`,
    type: item.step_type,
    status: item.status,
    message:
      item.error_message ??
      (item.score_value !== null
        ? `步骤执行完成，score=${item.score_value}`
        : '步骤执行完成。'),
    durationMs: item.duration_ms,
    scoreValue: item.score_value,
    expectedMediaObjectId: item.expected_media_object_id,
    actualMediaObjectId: item.actual_media_object_id,
    diffMediaObjectId: item.diff_media_object_id,
    parentStepNo: item.parent_step_no,
    branchKey: item.branch_key,
    branchName: item.branch_name,
    branchStepIndex: item.branch_step_index,
    repairResourceType: item.repair_resource_type,
    repairResourceId: item.repair_resource_id,
    repairRoutePath: item.repair_route_path,
    repairStepNo: item.repair_step_no,
    artifactLabel: item.diff_media_object_id
      ? `diff-media-object #${item.diff_media_object_id}`
      : item.actual_media_object_id
        ? `actual-media-object #${item.actual_media_object_id}`
        : undefined
  }
}

function calcDurationSeconds(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt || !finishedAt) {
    return 0
  }

  const duration = (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000
  return Math.max(0, Math.round(duration))
}

export async function listTestRuns(options?: { status?: string }): Promise<TestRun[]> {
  const params: Record<string, string | number> = { page: 1, page_size: 100 }
  if (options?.status) {
    params.status = options.status
  }

  const [response, reference] = await Promise.all([
    requestPage<TestRunReadDTO>({
      method: 'get',
      url: '/test-runs',
      params
    }),
    loadReferenceMaps()
  ])

  return response.data.map((item) => mapRun(item, reference))
}

export async function createTestRun(payload: {
  testSuiteId: number
  environmentProfileId: number
  deviceProfileId: number | null
}): Promise<TestRun> {
  const reference = await loadReferenceMaps()
  const response = await requestData<TestRunReadDTO>({
    method: 'post',
    url: '/test-runs',
    headers: {
      'Idempotency-Key': `run-${Date.now()}-${crypto.randomUUID()}`
    },
    data: {
      test_suite_id: payload.testSuiteId,
      environment_profile_id: payload.environmentProfileId,
      device_profile_id: payload.deviceProfileId,
      trigger_source: 'manual'
    }
  })

  return mapRun(response, reference)
}

export async function getRunDetail(testRunId: number): Promise<RunDetail> {
  const [testRun, caseRuns, reference] = await Promise.all([
    requestData<TestRunReadDTO>({
      method: 'get',
      url: `/test-runs/${testRunId}`
    }),
    requestData<TestCaseRunReadDTO[]>({
      method: 'get',
      url: `/test-runs/${testRunId}/case-runs`
    }),
    loadReferenceMaps()
  ])

  const suite = reference.suiteMap.get(testRun.test_suite_id)
  const environment = reference.environmentMap.get(testRun.environment_profile_id)
  const device = testRun.device_profile_id
    ? reference.deviceMap.get(testRun.device_profile_id)
    : null

  const caseRunsWithSteps = await Promise.all(
    caseRuns.map(async (caseRun) => {
      const steps = await requestData<StepResultReadDTO[]>({
        method: 'get',
        url: `/case-runs/${caseRun.id}/step-results`
      })
      const testCase = reference.caseMap.get(caseRun.test_case_id)

      return {
        id: caseRun.id,
        testCaseId: caseRun.test_case_id,
        name: testCase?.case_name ?? `测试用例 #${caseRun.test_case_id}`,
        status: caseRun.status,
        durationMs: caseRun.duration_ms ?? 0,
        diffCount: steps.filter((item) => item.diff_media_object_id !== null).length,
        failureSummary:
          caseRun.failure_summary ??
          caseRun.failure_reason_code ??
          '当前用例未记录失败摘要。',
        sortOrder: caseRun.sort_order,
        steps: steps.map(mapStepResult)
      }
    })
  )

  return {
    id: testRun.id,
    testRunId: testRun.id,
    testSuiteId: testRun.test_suite_id,
    environmentProfileId: testRun.environment_profile_id,
    deviceProfileId: testRun.device_profile_id,
    suiteName: suite?.suite_name ?? `套件 #${testRun.test_suite_id}`,
    environmentName:
      environment?.profile_name ?? `环境 #${testRun.environment_profile_id}`,
    deviceName: device?.profile_name ?? '未指定设备',
    status: testRun.status,
    createdAt: testRun.created_at,
    startedAt: testRun.started_at,
    finishedAt: testRun.finished_at,
    summary: {
      totalCases: testRun.total_case_count,
      passedCases: testRun.passed_case_count,
      failedCases: testRun.failed_case_count,
      errorCases: testRun.error_case_count,
      durationSeconds: calcDurationSeconds(testRun.started_at, testRun.finished_at)
    },
    caseRuns: caseRunsWithSteps
  }
}

function mapReportSummary(item: ReportSummaryDTO): ReportSummary {
  return {
    status: item.status,
    counts: {
      total: item.counts.total,
      passed: item.counts.passed,
      failed: item.counts.failed,
      error: item.counts.error,
      cancelled: item.counts.cancelled
    },
    failure: item.failure
      ? {
          code: item.failure.code,
          summary: item.failure.summary
        }
      : null,
    timing: {
      startedAt: item.timing.started_at,
      finishedAt: item.timing.finished_at,
      durationMs: item.timing.duration_ms
    },
    artifacts: {
      total: item.artifacts.total,
      byType: item.artifacts.by_type
    },
    totalCaseCount: item.total_case_count,
    passedCaseCount: item.passed_case_count,
    failedCaseCount: item.failed_case_count,
    errorCaseCount: item.error_case_count,
    cancelledCaseCount: item.cancelled_case_count,
    message: item.message
  }
}

function mapRunReport(item: RunReportReadDTO): RunReport {
  return {
    id: item.id,
    testRunId: item.test_run_id,
    status: item.summary_status,
    summary: mapReportSummary(item.summary_json),
    generatedAt: item.generated_at,
    createdAt: item.created_at
  }
}

function mapReportArtifact(item: ReportArtifactReadDTO): ReportArtifact {
  return {
    id: item.id,
    reportId: item.report_id,
    artifactType: item.artifact_type,
    mediaObjectId: item.media_object_id,
    caseRunId: item.case_run_id,
    stepResultId: item.step_result_id,
    artifactUrl: item.artifact_url,
    createdAt: item.created_at
  }
}

export async function getTestRunReport(testRunId: number): Promise<RunReport | null> {
  try {
    const response = await requestData<RunReportReadDTO>({
      method: 'get',
      url: `/test-runs/${testRunId}/report`
    })

    return mapRunReport(response)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'REPORT_NOT_FOUND') {
      return null
    }

    throw error
  }
}

export async function listReportArtifacts(reportId: number): Promise<ReportArtifact[]> {
  const response = await requestData<ReportArtifactReadDTO[]>({
    method: 'get',
    url: `/reports/${reportId}/artifacts`
  })

  return response.map(mapReportArtifact)
}
