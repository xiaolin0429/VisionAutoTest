import { computed, reactive, ref, type Ref } from 'vue'
import type { Template } from '@/types/models'

export interface TemplateDialogFormState {
  templateCode: string
  templateName: string
  templateType: string
  matchStrategy: string
  thresholdValue: number | null
  status: string
}

export interface BaselineRevisionFormState {
  remark: string
  isCurrent: boolean
}

export const templateTypeOptions = [
  { label: '页面模板', value: 'page' },
  { label: '组件模板', value: 'component' },
  { label: '文本区域', value: 'text_region' }
] as const

export const matchStrategyOptions = [
  { label: 'Template', value: 'template' },
  { label: 'OCR', value: 'ocr' }
] as const

export const templateStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '归档', value: 'archived' }
] as const

export function trimTemplateText(value: string) {
  return value.trim()
}

export function isTemplateThresholdValueValid(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

function createDefaultTemplateFormState(): TemplateDialogFormState {
  return {
    templateCode: '',
    templateName: '',
    templateType: 'page',
    matchStrategy: 'template',
    thresholdValue: 0.95,
    status: 'draft'
  }
}

function createDefaultBaselineRevisionFormState(): BaselineRevisionFormState {
  return {
    remark: '',
    isCurrent: true
  }
}

export function useTemplateDialogs(currentTemplate: Ref<Template | null>) {
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const baselineDialogVisible = ref(false)

  const createForm = reactive<TemplateDialogFormState>(createDefaultTemplateFormState())
  const editForm = reactive<TemplateDialogFormState>(createDefaultTemplateFormState())
  const baselineForm = reactive<BaselineRevisionFormState>(
    createDefaultBaselineRevisionFormState()
  )

  const createSourceFile = ref<File | null>(null)
  const baselineFile = ref<File | null>(null)

  function resetCreateForm() {
    Object.assign(createForm, createDefaultTemplateFormState())
    createSourceFile.value = null
  }

  function resetEditForm() {
    if (!currentTemplate.value) {
      Object.assign(editForm, createDefaultTemplateFormState())
      return
    }

    Object.assign(editForm, {
      templateCode: currentTemplate.value.code,
      templateName: currentTemplate.value.name,
      templateType: currentTemplate.value.templateType,
      matchStrategy: currentTemplate.value.matchStrategy,
      thresholdValue: currentTemplate.value.thresholdValue,
      status: currentTemplate.value.status
    })
  }

  function resetBaselineForm() {
    Object.assign(baselineForm, createDefaultBaselineRevisionFormState())
    baselineFile.value = null
  }

  function openCreateDialog() {
    resetCreateForm()
    createDialogVisible.value = true
  }

  function closeCreateDialog() {
    createDialogVisible.value = false
    resetCreateForm()
  }

  function openEditDialog() {
    resetEditForm()
    editDialogVisible.value = true
  }

  function closeEditDialog() {
    editDialogVisible.value = false
    resetEditForm()
  }

  function openBaselineDialog() {
    resetBaselineForm()
    baselineDialogVisible.value = true
  }

  function closeBaselineDialog() {
    baselineDialogVisible.value = false
    resetBaselineForm()
  }

  function setCreateSourceFile(file: File | null) {
    createSourceFile.value = file
  }

  function setBaselineFile(file: File | null) {
    baselineFile.value = file
  }

  const createCodeError = computed(() => {
    return trimTemplateText(createForm.templateCode) ? '' : '请输入模板编码。'
  })

  const createNameError = computed(() => {
    return trimTemplateText(createForm.templateName) ? '' : '请输入模板名称。'
  })

  const createThresholdError = computed(() => {
    return isTemplateThresholdValueValid(createForm.thresholdValue)
      ? ''
      : '请输入 0 ~ 1 的匹配阈值。'
  })

  const createFileError = computed(() => {
    return createSourceFile.value ? '' : '请先选择原始模板文件。'
  })

  const editNameError = computed(() => {
    return trimTemplateText(editForm.templateName) ? '' : '请输入模板名称。'
  })

  const editThresholdError = computed(() => {
    return isTemplateThresholdValueValid(editForm.thresholdValue)
      ? ''
      : '请输入 0 ~ 1 的匹配阈值。'
  })

  const baselineActionLabel = computed(() => {
    return baselineForm.isCurrent ? '上传并设为当前版本' : '上传基准版本'
  })

  const baselineSubmitSuccessMessage = computed(() => {
    return baselineForm.isCurrent ? '基准版本已新增并设为当前版本。' : '基准版本已新增。'
  })

  const canSubmitCreate = computed(() => {
    return Boolean(
      !createCodeError.value &&
        !createNameError.value &&
        !createThresholdError.value &&
        !createFileError.value &&
        createForm.templateType &&
        createForm.matchStrategy &&
        createForm.status
    )
  })

  const canSubmitEdit = computed(() => {
    return Boolean(
      currentTemplate.value &&
        !editNameError.value &&
        !editThresholdError.value &&
        editForm.templateType &&
        editForm.matchStrategy &&
        editForm.status
    )
  })

  const canSubmitBaseline = computed(() => {
    return Boolean(currentTemplate.value && baselineFile.value)
  })

  return {
    createDialogVisible,
    editDialogVisible,
    baselineDialogVisible,
    createForm,
    editForm,
    baselineForm,
    createSourceFile,
    baselineFile,
    resetCreateForm,
    resetEditForm,
    resetBaselineForm,
    openCreateDialog,
    closeCreateDialog,
    openEditDialog,
    closeEditDialog,
    openBaselineDialog,
    closeBaselineDialog,
    setCreateSourceFile,
    setBaselineFile,
    createCodeError,
    createNameError,
    createThresholdError,
    createFileError,
    editNameError,
    editThresholdError,
    baselineActionLabel,
    baselineSubmitSuccessMessage,
    canSubmitCreate,
    canSubmitEdit,
    canSubmitBaseline
  }
}
