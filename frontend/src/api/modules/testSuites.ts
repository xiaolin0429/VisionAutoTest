import { requestData, requestPage } from '@/api/client'
import type {
  ExecutionReadinessSummaryReadDTO,
  SuiteCaseDTO,
  TestCaseReadDTO,
  TestSuiteReadDTO
} from '@/types/backend'
import type {
  ExecutionReadinessSummary,
  SuiteCaseWritePayload,
  TestSuite,
  TestSuiteCreatePayload,
  TestSuiteUpdatePayload
} from '@/types/models'

function mapTestSuiteSummary(item: TestSuiteReadDTO): TestSuite {
  // @param item Backend suite summary DTO.
  return {
    id: item.id,
    code: item.suite_code,
    name: item.suite_name,
    status: item.status,
    description: item.description ?? '',
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    cases: []
  }
}

function mapExecutionReadiness(
  item: ExecutionReadinessSummaryReadDTO
): ExecutionReadinessSummary {
  // @param item Backend readiness DTO for the suite execution gate.
  return {
    scope: item.scope,
    status: item.status,
    workspaceId: item.workspace_id,
    testSuiteId: item.test_suite_id,
    activeEnvironmentCount: item.active_environment_count,
    activeTestSuiteCount: item.active_test_suite_count,
    blockingIssueCount: item.blocking_issue_count,
    issues: item.issues.map((issue) => ({
      code: issue.code,
      message: issue.message,
      resourceType: issue.resource_type,
      resourceId: issue.resource_id,
      resourceName: issue.resource_name ?? '',
      routePath: issue.route_path
    }))
  }
}

async function listCaseIndex() {
  // Loads a case lookup map so suite-case rows can display case names and statuses.
  const response = await requestPage<TestCaseReadDTO>({
    method: 'get',
    url: '/test-cases',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return new Map(response.data.map((item) => [item.id, item]))
}

export async function listTestSuites(): Promise<TestSuite[]> {
  // Loads suite summaries for list pages and trigger dialogs.
  const response = await requestPage<TestSuiteReadDTO>({
    method: 'get',
    url: '/test-suites',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return response.data.map(mapTestSuiteSummary)
}

export async function getTestSuiteDetail(testSuiteId: number): Promise<TestSuite> {
  // @param testSuiteId Suite id whose summary and ordered case list should be aggregated.
  const [suite, suiteCases, caseIndex] = await Promise.all([
    requestData<TestSuiteReadDTO>({
      method: 'get',
      url: `/test-suites/${testSuiteId}`
    }),
    requestData<SuiteCaseDTO[]>({
      method: 'get',
      url: `/test-suites/${testSuiteId}/cases`
    }),
    listCaseIndex()
  ])

  return {
    ...mapTestSuiteSummary(suite),
    cases: suiteCases.map((item) => {
      const testCase = caseIndex.get(item.test_case_id)
      return {
        id: item.id,
        testCaseId: item.test_case_id,
        name: testCase?.case_name ?? `测试用例 #${item.test_case_id}`,
        orderNo: item.sort_order,
        status: testCase?.status ?? 'unknown',
        createdAt: item.created_at
      }
    })
  }
}

export async function createTestSuite(payload: TestSuiteCreatePayload): Promise<TestSuite> {
  // @param payload Frontend create payload for a suite.
  const response = await requestData<TestSuiteReadDTO>({
    method: 'post',
    url: '/test-suites',
    data: {
      suite_code: payload.code,
      suite_name: payload.name,
      status: payload.status,
      description: payload.description
    }
  })

  return mapTestSuiteSummary(response)
}

export async function updateTestSuite(
  testSuiteId: number,
  payload: TestSuiteUpdatePayload
): Promise<TestSuite> {
  // @param testSuiteId Suite id being updated.
  // @param payload Frontend update payload.
  const response = await requestData<TestSuiteReadDTO>({
    method: 'patch',
    url: `/test-suites/${testSuiteId}`,
    data: {
      suite_name: payload.name,
      status: payload.status,
      description: payload.description
    }
  })

  return mapTestSuiteSummary(response)
}

export async function replaceSuiteCases(
  testSuiteId: number,
  payload: SuiteCaseWritePayload[]
): Promise<void> {
  // @param testSuiteId Suite id whose case ordering should be fully replaced.
  // @param payload Ordered suite-case payload list.
  await requestData<SuiteCaseDTO[]>({
    method: 'put',
    url: `/test-suites/${testSuiteId}/cases`,
    data: payload.map((item) => ({
      test_case_id: item.testCaseId,
      sort_order: item.sortOrder
    }))
  })
}

export async function getTestSuiteExecutionReadiness(
  testSuiteId: number
): Promise<ExecutionReadinessSummary> {
  // @param testSuiteId Suite id whose execution-readiness summary should be loaded.
  const response = await requestData<ExecutionReadinessSummaryReadDTO>({
    method: 'get',
    url: `/test-suites/${testSuiteId}/execution-readiness`
  })

  return mapExecutionReadiness(response)
}
