import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { useStepEditor } from '@/composables/useStepEditor'
import type { StepWritePayload } from '@/types/models'
import {
  createEmptyStepDraft,
  type StepDraft
} from '@/utils/steps'

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn()
  }
}))

function createNavigateDraft(index: number): StepDraft {
  const draft = createEmptyStepDraft(index)
  draft.type = 'navigate'
  draft.name = '打开登录页'
  draft.url = '/login'
  return draft
}

describe('useStepEditor save integration', (): void => {
  it('builds a complete payload from StepDraft order with continuous step numbers', async (): Promise<void> => {
    const editor = useStepEditor({ allowComponentCall: true })
    const waitDraft = createEmptyStepDraft(0)
    waitDraft.stepNo = 20
    const navigateDraft = createNavigateDraft(1)
    navigateDraft.stepNo = 40
    editor.normalizeStepDrafts([navigateDraft, waitDraft])
    const saveFn = vi.fn(
      async (_payload: StepWritePayload[]): Promise<void> => undefined
    )

    const success = await editor.saveSteps(saveFn)

    expect(success).toBe(true)
    expect(saveFn).toHaveBeenCalledTimes(1)
    const payload = saveFn.mock.calls[0][0]
    expect(payload.map((item: StepWritePayload): number => item.stepNo)).toEqual([
      1,
      2
    ])
    expect(payload.map((item: StepWritePayload): string => item.type)).toEqual([
      'navigate',
      'wait'
    ])
  })

  it('blocks submission when draft validation fails', async (): Promise<void> => {
    const editor = useStepEditor({ allowComponentCall: true })
    const invalidDraft = createEmptyStepDraft(0)
    invalidDraft.type = 'click'
    invalidDraft.selector = ''
    editor.normalizeStepDrafts([invalidDraft])
    const saveFn = vi.fn(
      async (_payload: StepWritePayload[]): Promise<void> => undefined
    )

    const success = await editor.saveSteps(saveFn)

    expect(success).toBe(false)
    expect(saveFn).not.toHaveBeenCalled()
    expect(editor.stepSubmitAttempted.value).toBe(true)
  })

  it('keeps drafts and exposes STEP_CONFIGURATION_INVALID until the next edit', async (): Promise<void> => {
    const editor = useStepEditor({ allowComponentCall: true })
    editor.normalizeStepDrafts([createEmptyStepDraft(0)])
    const originalDrafts = JSON.stringify(editor.stepDrafts.value)

    const success = await editor.saveSteps(
      async (_payload: StepWritePayload[]): Promise<void> => {
        throw new ApiError(
          'STEP_CONFIGURATION_INVALID',
          '服务端拒绝了步骤配置。',
          422
        )
      }
    )

    expect(success).toBe(false)
    expect(JSON.stringify(editor.stepDrafts.value)).toBe(originalDrafts)
    expect(editor.stepSaveError.value).toEqual({
      code: 'STEP_CONFIGURATION_INVALID',
      message: '服务端拒绝了步骤配置。'
    })

    editor.normalizeStepDrafts([...editor.stepDrafts.value])
    expect(editor.stepSaveError.value).toBeNull()
  })
})
