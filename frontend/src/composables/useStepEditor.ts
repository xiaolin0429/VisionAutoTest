import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import {
  buildStepDraft,
  buildStepWritePayload,
  createEmptyStepDraft,
  createStepTypeOptions,
  normalizeStepByType,
  normalizeStepDrafts as normalizeStepDraftItems,
  shouldOpenAdvancedPayload as shouldOpenAdvancedPayloadDraft,
  validateStepDraft,
  type StepDraft,
  type StepValidationErrors
} from '@/utils/steps'
import type { Step, StepType, StepWritePayload } from '@/types/models'

export interface UseStepEditorOptions {
  allowComponentCall: boolean
}

export interface StepEditorSaveError {
  code: string
  message: string
}

export function useStepEditor(options: UseStepEditorOptions) {
  const stepDrafts = ref<StepDraft[]>([])
  const savingSteps = ref(false)
  const stepSubmitAttempted = ref(false)
  const stepSaveError = ref<StepEditorSaveError | null>(null)

  const stepTypeOptions = createStepTypeOptions({
    allowComponentCall: options.allowComponentCall
  })

  function validateStep(step: StepDraft): StepValidationErrors {
    return validateStepDraft(step)
  }

  const stepValidationErrors = computed((): StepValidationErrors[] => {
    return stepDrafts.value.map(
      (step: StepDraft): StepValidationErrors => validateStep(step)
    )
  })

  const hasStepValidationErrors = computed((): boolean => {
    return stepValidationErrors.value.some(
      (item: StepValidationErrors): boolean => Object.keys(item).length > 0
    )
  })

  function normalizeStepDrafts(items: StepDraft[]): void {
    // @param items Step drafts in arbitrary order or shape before standard editor normalization.
    stepDrafts.value = normalizeStepDraftItems(items)
    stepSaveError.value = null
  }

  function getStepError(
    index: number,
    field: keyof StepValidationErrors
  ): string {
    // @param index Step index in the current draft list.
    // @param field Validation field name to read from the computed error map.
    return stepValidationErrors.value[index]?.[field] ?? ''
  }

  function updateStepType(step: StepDraft, nextType: StepType): void {
    // @param step Mutable draft that should be reshaped to the newly selected type.
    // @param nextType Target step type chosen by the user.
    Object.assign(step, normalizeStepByType(step, nextType))
  }

  function handleStepTypeModelUpdate(
    step: StepDraft,
    value: string | number | boolean
  ): void {
    // @param step Mutable draft bound to the current editor row.
    // @param value Raw component-model value narrowed back to a StepType.
    updateStepType(step, value as StepType)
  }

  function initFromSteps(steps: Step[]): void {
    // @param steps Persisted steps loaded from the backend for the current resource.
    stepSubmitAttempted.value = false
    normalizeStepDrafts(
      steps.map((step: Step): StepDraft => buildStepDraft(step))
    )
    if (stepDrafts.value.length === 0) {
      normalizeStepDrafts([createEmptyStepDraft(0)])
    }
  }

  function addStep(): void {
    normalizeStepDrafts([...stepDrafts.value, createEmptyStepDraft(stepDrafts.value.length)])
  }

  function removeStep(index: number): void {
    normalizeStepDrafts(
      stepDrafts.value.filter(
        (_step: StepDraft, currentIndex: number): boolean =>
          currentIndex !== index
      )
    )
    if (stepDrafts.value.length === 0) {
      normalizeStepDrafts([createEmptyStepDraft(0)])
    }
  }

  function moveStep(index: number, direction: -1 | 1): void {
    const nextIndex = index + direction
    if (nextIndex < 0 || nextIndex >= stepDrafts.value.length) {
      return
    }

    const nextDrafts = [...stepDrafts.value]
    const [currentItem] = nextDrafts.splice(index, 1)
    nextDrafts.splice(nextIndex, 0, currentItem)
    normalizeStepDrafts(nextDrafts)
  }

  function shouldOpenAdvancedPayload(index: number): boolean {
    // @param index Step index whose payload editor mode should be evaluated.
    const draft = stepDrafts.value[index]
    if (!draft) {
      return false
    }
    return shouldOpenAdvancedPayloadDraft(draft)
  }

  function buildPayload(): StepWritePayload[] {
    // @returns Step write payload in backend save order with normalized step numbers.
    return stepDrafts.value.map(
      (step: StepDraft, index: number): StepWritePayload =>
        buildStepWritePayload(step, index)
    )
  }

  async function saveSteps(
    saveFn: (payload: StepWritePayload[]) => Promise<void>
  ): Promise<boolean> {
    // @param saveFn Caller-provided save implementation for component/case step persistence.
    // @returns True when save succeeds, otherwise false after local validation or request failure.
    stepSubmitAttempted.value = true
    stepSaveError.value = null

    if (hasStepValidationErrors.value) {
      ElMessage.error('请修正步骤配置后再保存。')
      return false
    }

    savingSteps.value = true
    try {
      const payload = buildPayload()
      await saveFn(payload)
      stepSubmitAttempted.value = false
      ElMessage.success('步骤编排已保存。')
      return true
    } catch (error: unknown) {
      const message =
        error instanceof ApiError && error.code === 'STEP_CONFIGURATION_INVALID'
          ? error.message
          : '步骤保存失败，请稍后重试。'
      stepSaveError.value = {
        code: error instanceof ApiError ? error.code : 'STEP_SAVE_FAILED',
        message
      }
      ElMessage.error(message)
      return false
    } finally {
      savingSteps.value = false
    }
  }

  function resetState(): void {
    // Clears transient submit state without modifying the current draft list.
    stepSubmitAttempted.value = false
    stepSaveError.value = null
  }

  return {
    stepDrafts,
    savingSteps,
    stepSubmitAttempted,
    stepSaveError,
    stepTypeOptions,
    stepValidationErrors,
    hasStepValidationErrors,
    validateStep,
    normalizeStepDrafts,
    getStepError,
    updateStepType,
    handleStepTypeModelUpdate,
    initFromSteps,
    addStep,
    removeStep,
    moveStep,
    shouldOpenAdvancedPayload,
    buildPayload,
    saveSteps,
    resetState
  }
}
