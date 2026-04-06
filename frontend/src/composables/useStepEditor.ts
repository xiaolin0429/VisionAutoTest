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

export function useStepEditor(options: UseStepEditorOptions) {
  const stepDrafts = ref<StepDraft[]>([])
  const savingSteps = ref(false)
  const stepSubmitAttempted = ref(false)

  const stepTypeOptions = createStepTypeOptions({
    allowComponentCall: options.allowComponentCall
  })

  const stepValidationErrors = computed(() => {
    return stepDrafts.value.map((step) => validateStepDraft(step))
  })

  const hasStepValidationErrors = computed(() => {
    return stepValidationErrors.value.some((item) => Object.keys(item).length > 0)
  })

  function normalizeStepDrafts(items: StepDraft[]) {
    // @param items Step drafts in arbitrary order or shape before standard editor normalization.
    stepDrafts.value = normalizeStepDraftItems(items)
  }

  function getStepError(index: number, field: keyof StepValidationErrors) {
    // @param index Step index in the current draft list.
    // @param field Validation field name to read from the computed error map.
    return stepValidationErrors.value[index]?.[field] ?? ''
  }

  function updateStepType(step: StepDraft, nextType: StepType) {
    // @param step Mutable draft that should be reshaped to the newly selected type.
    // @param nextType Target step type chosen by the user.
    Object.assign(step, normalizeStepByType(step, nextType))
  }

  function handleStepTypeModelUpdate(step: StepDraft, value: string | number | boolean) {
    // @param step Mutable draft bound to the current editor row.
    // @param value Raw component-model value narrowed back to a StepType.
    updateStepType(step, value as StepType)
  }

  function initFromSteps(steps: Step[]) {
    // @param steps Persisted steps loaded from the backend for the current resource.
    stepSubmitAttempted.value = false
    normalizeStepDrafts(steps.map((step) => buildStepDraft(step)))
    if (stepDrafts.value.length === 0) {
      normalizeStepDrafts([createEmptyStepDraft(0)])
    }
  }

  function addStep() {
    normalizeStepDrafts([...stepDrafts.value, createEmptyStepDraft(stepDrafts.value.length)])
  }

  function removeStep(index: number) {
    normalizeStepDrafts(stepDrafts.value.filter((_, currentIndex) => currentIndex !== index))
    if (stepDrafts.value.length === 0) {
      normalizeStepDrafts([createEmptyStepDraft(0)])
    }
  }

  function moveStep(index: number, direction: -1 | 1) {
    const nextIndex = index + direction
    if (nextIndex < 0 || nextIndex >= stepDrafts.value.length) {
      return
    }

    const nextDrafts = [...stepDrafts.value]
    const [currentItem] = nextDrafts.splice(index, 1)
    nextDrafts.splice(nextIndex, 0, currentItem)
    normalizeStepDrafts(nextDrafts)
  }

  function shouldOpenAdvancedPayload(index: number) {
    // @param index Step index whose payload editor mode should be evaluated.
    const draft = stepDrafts.value[index]
    if (!draft) {
      return false
    }
    return shouldOpenAdvancedPayloadDraft(draft)
  }

  function buildPayload(): StepWritePayload[] {
    // @returns Step write payload in backend save order with normalized step numbers.
    return stepDrafts.value.map((step, index) => buildStepWritePayload(step, index))
  }

  async function saveSteps(saveFn: (payload: StepWritePayload[]) => Promise<void>) {
    // @param saveFn Caller-provided save implementation for component/case step persistence.
    // @returns True when save succeeds, otherwise false after local validation or request failure.
    stepSubmitAttempted.value = true

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
    } catch (error) {
      const message =
        error instanceof ApiError && error.code === 'STEP_CONFIGURATION_INVALID'
          ? error.message
          : '步骤保存失败，请稍后重试。'
      ElMessage.error(message)
      return false
    } finally {
      savingSteps.value = false
    }
  }

  function resetState() {
    // Clears transient submit state without modifying the current draft list.
    stepSubmitAttempted.value = false
  }

  return {
    stepDrafts,
    savingSteps,
    stepSubmitAttempted,
    stepTypeOptions,
    stepValidationErrors,
    hasStepValidationErrors,
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
