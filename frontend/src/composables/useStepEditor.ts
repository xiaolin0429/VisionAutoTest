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
    stepDrafts.value = normalizeStepDraftItems(items)
  }

  function getStepError(index: number, field: keyof StepValidationErrors) {
    return stepValidationErrors.value[index]?.[field] ?? ''
  }

  function updateStepType(step: StepDraft, nextType: StepType) {
    Object.assign(step, normalizeStepByType(step, nextType))
  }

  function handleStepTypeModelUpdate(step: StepDraft, value: string | number | boolean) {
    updateStepType(step, value as StepType)
  }

  function initFromSteps(steps: Step[]) {
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
    const draft = stepDrafts.value[index]
    if (!draft) {
      return false
    }
    return shouldOpenAdvancedPayloadDraft(draft)
  }

  function buildPayload(): StepWritePayload[] {
    return stepDrafts.value.map((step, index) => buildStepWritePayload(step, index))
  }

  async function saveSteps(saveFn: (payload: StepWritePayload[]) => Promise<void>) {
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
