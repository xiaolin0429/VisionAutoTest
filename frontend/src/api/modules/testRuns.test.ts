import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getRunDetail, getTestRunReport } from '@/api/modules/testRuns'

const client = vi.hoisted(() => ({
  requestData: vi.fn(),
  requestPage: vi.fn()
}))

vi.mock('@/api/client', () => ({
  ApiError: class ApiError extends Error {},
  requestData: client.requestData,
  requestPage: client.requestPage
}))

beforeEach((): void => {
  client.requestData.mockReset()
  client.requestPage.mockReset()
})

describe('test run result metadata mapping', (): void => {
  it('mirrors result_metadata_json into the step result model', async (): Promise<void> => {
    client.requestPage.mockImplementation(
      async ({ url }: { url: string }): Promise<{ data: unknown[] }> => {
        if (url === '/test-suites') {
          return {
            data: [{ id: 2, suite_name: 'OCR Suite' }]
          }
        }
        if (url === '/environment-profiles') {
          return {
            data: [{ id: 3, profile_name: 'Test' }]
          }
        }
        if (url === '/test-cases') {
          return {
            data: [{ id: 5, case_name: 'OCR Case' }]
          }
        }
        return { data: [] }
      }
    )
    client.requestData.mockImplementation(
      async ({ url }: { url: string }): Promise<unknown> => {
        if (url === '/test-runs/1') {
          return {
            id: 1,
            test_suite_id: 2,
            environment_profile_id: 3,
            device_profile_id: null,
            status: 'passed',
            created_at: '2026-08-16T00:00:00Z',
            started_at: '2026-08-16T00:00:00Z',
            finished_at: '2026-08-16T00:00:01Z',
            total_case_count: 1,
            passed_case_count: 1,
            failed_case_count: 0,
            error_case_count: 0
          }
        }
        if (url === '/test-runs/1/case-runs') {
          return [
            {
              id: 4,
              test_case_id: 5,
              status: 'passed',
              duration_ms: 10,
              failure_summary: null,
              failure_reason_code: null,
              sort_order: 1
            }
          ]
        }
        return [
          {
            id: 6,
            step_no: 1,
            step_name: '提交表单',
            step_type: 'click',
            status: 'passed',
            score_value: 0.95,
            expected_media_object_id: null,
            actual_media_object_id: null,
            diff_media_object_id: null,
            error_message: null,
            duration_ms: 8,
            parent_step_no: null,
            branch_key: null,
            branch_name: null,
            branch_step_index: null,
            result_metadata_json: {
              ocr: {
                scope: 'viewport',
                language: 'zh_en',
                matched_text: '提交',
                role: 'button',
                confidence: 0.96,
                score: 0.93,
                candidate_count: 1,
                candidates: [
                  {
                    rank: 1,
                    matched_text: '提交',
                    role: 'button',
                    confidence: 0.96,
                    score: 0.93,
                    viewport_css_rect: { x: 10, y: 20, width: 80, height: 24 },
                    document_css_rect: { x: 10, y: 120, width: 80, height: 24 }
                  }
                ],
                preprocess_variants: ['original'],
                tiles: { scanned: 1, captured: 1 },
                cache: {
                  analysis_hits: 0,
                  analysis_misses: 1,
                  snapshot_hits: 0,
                  snapshot_misses: 1
                },
                revalidation: { required: false, attempted: false, passed: null },
                duration_ms: { ocr: 4.2, locate: 6.8 }
              }
            },
            repair_resource_type: 'test_case',
            repair_resource_id: 5,
            repair_route_path: '/cases',
            repair_step_no: 1
          }
        ]
      }
    )

    const detail = await getRunDetail(1)

    expect(detail.caseRuns[0].steps[0].resultMetadata).toMatchObject({
      ocr: {
        scope: 'viewport',
        language: 'zh_en',
        matchedText: '提交',
        role: 'button',
        confidence: 0.96,
        score: 0.93,
        candidateCount: 1,
        preprocessVariants: ['original'],
        tiles: { scanned: 1, captured: 1 },
        durationMs: { ocr: 4.2, locate: 6.8 },
        candidates: [
          {
            rank: 1,
            matchedText: '提交',
            viewportCssRect: { x: 10, y: 20, width: 80, height: 24 },
            documentCssRect: { x: 10, y: 120, width: 80, height: 24 }
          }
        ]
      }
    })
    expect(detail.caseRuns[0].steps[0].name).toBe('提交表单')
  })

  it('maps a structured report repair target without parsing its summary', async (): Promise<void> => {
    client.requestData.mockResolvedValue({
      id: 8,
      test_run_id: 7,
      summary_status: 'error',
      summary_json: {
        status: 'error',
        counts: { total: 1, passed: 0, failed: 0, error: 1, cancelled: 0 },
        failure: {
          code: 'ENVIRONMENT_BASE_URL_INVALID',
          summary: '执行环境地址无效',
          repair_target: {
            resource_type: 'environment_profile',
            resource_id: 3,
            resource_name: '预发环境',
            route_path: '/environments',
            step_no: null
          }
        },
        timing: { started_at: null, finished_at: null, duration_ms: null },
        artifacts: { total: 0, by_type: {} },
        total_case_count: 1,
        passed_case_count: 0,
        failed_case_count: 0,
        error_case_count: 1,
        cancelled_case_count: 0,
        message: null
      },
      generated_at: '2026-08-27T00:00:00Z',
      created_at: '2026-08-27T00:00:00Z'
    })

    const report = await getTestRunReport(7)

    expect(report?.summary.failure?.repairTarget).toEqual({
      resourceType: 'environment_profile',
      resourceId: 3,
      resourceName: '预发环境',
      routePath: '/environments',
      stepNo: null
    })
  })
})
