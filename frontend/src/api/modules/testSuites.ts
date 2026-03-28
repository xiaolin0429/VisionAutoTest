import { requestData, requestPage } from '@/api/client'
import type {
  SuiteCaseDTO,
  TestCaseReadDTO,
  TestSuiteReadDTO
} from '@/types/backend'
import type { TestSuite } from '@/types/models'

function mapTestSuiteSummary(item: TestSuiteReadDTO): TestSuite {
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

async function listCaseIndex() {
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
