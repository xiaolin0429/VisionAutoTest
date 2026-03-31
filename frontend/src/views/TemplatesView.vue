<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError, requestBlob } from '@/api/client'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TemplateCanvas from '@/components/TemplateCanvas.vue'
import { createMediaObject, getMediaObjectContent } from '@/api/modules/mediaObjects'
import {
  createBaselineRevision,
  createMaskRegion,
  createTemplate,
  deleteMaskRegion,
  getTemplateProcessedPreview,
  getTemplateDetail,
  listTemplates,
  listTemplateOcrResults,
  requestTemplateOcrAnalysis,
  updateMaskRegion,
  updateTemplate,
  type ListTemplatesParams
} from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import type {
  BaselineRevision,
  MaskRegion,
  Template,
  TemplateOcrBlock,
  TemplateEditorMode,
  TemplateMaskDraft,
  TemplateOcrResult,
  TemplatePreviewState,
  TemplateWorkbenchViewMode
} from '@/types/models'

interface OcrPanelState {
  status: 'idle' | 'loading' | 'not_generated' | 'ready' | 'error'
  baselineRevisionId: number | null
  message: string
}

const templateTypeOptions = [
  { label: '页面模板', value: 'page' },
  { label: '组件模板', value: 'component' },
  { label: '文本区域', value: 'text_region' }
] as const

const matchStrategyOptions = [
  { label: 'Template', value: 'template' },
  { label: 'OCR', value: 'ocr' }
] as const

const templateStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '归档', value: 'archived' }
] as const

const listLoading = ref(false)
const detailLoading = ref(false)
const maskSaving = ref(false)
const createSubmitting = ref(false)
const editSubmitting = ref(false)
const baselineSubmitting = ref(false)
const listError = ref('')
const detailError = ref('')

const templates = ref<Template[]>([])
const selectedTemplateId = ref<number | null>(null)
const currentTemplate = ref<Template | null>(null)
const editorMode = ref<TemplateEditorMode>('view')
const selectedMaskId = ref<number | null>(null)
const draftMaskRegions = ref<TemplateMaskDraft[]>([])
const mediaObjectNameCache = ref<Record<number, string>>({})

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const baselineDialogVisible = ref(false)

const createFileInputRef = ref<HTMLInputElement | null>(null)
const baselineFileInputRef = ref<HTMLInputElement | null>(null)
const createSourceFile = ref<File | null>(null)
const baselineFile = ref<File | null>(null)

const listFilters = reactive({
  keyword: '',
  status: '',
  templateType: ''
})

const createForm = reactive({
  templateCode: '',
  templateName: '',
  templateType: 'page',
  matchStrategy: 'template',
  thresholdValue: 0.95 as number | null,
  status: 'draft'
})

const editForm = reactive({
  templateName: '',
  templateType: 'page',
  matchStrategy: 'template',
  thresholdValue: 0.95 as number | null,
  status: 'draft'
})

const baselineForm = reactive({
  remark: '',
  isCurrent: true
})

const workbenchViewMode = ref<TemplateWorkbenchViewMode>('mask')
const selectedBaselineRevisionId = ref<number | null>(null)
const baselinePreviewUrl = ref('')
const baselinePreviewLoading = ref(false)
const baselinePreviewError = ref('')
const previewUrlCache = ref<Record<number, string>>({})
const ocrPanelState = ref<OcrPanelState>({
  status: 'idle',
  baselineRevisionId: null,
  message: '当前基准版本尚未生成 OCR 结果。'
})
const processedPreviewState = ref<TemplatePreviewState>({
  status: 'idle',
  baselineRevisionId: null,
  sourceMediaObjectId: null,
  overlayMediaObjectId: null,
  overlayImageUrl: null,
  processedMediaObjectId: null,
  processedImageUrl: null,
  imageWidth: null,
  imageHeight: null,
  maskRegions: [],
  message: 'Mask 处理后预览尚未生成。'
})
const ocrSnapshot = ref<TemplateOcrResult | null>(null)
const selectedOcrResultId = ref<string | null>(null)

function createIdlePreviewState(message: string, baselineRevisionId: number | null): TemplatePreviewState {
  return {
    status: 'idle',
    baselineRevisionId,
    sourceMediaObjectId: null,
    overlayMediaObjectId: null,
    overlayImageUrl: null,
    processedMediaObjectId: null,
    processedImageUrl: null,
    imageWidth: null,
    imageHeight: null,
    maskRegions: [],
    message
  }
}

function createIdleOcrState(
  message: string,
  baselineRevisionId: number | null,
  status: OcrPanelState['status'] = 'idle'
): OcrPanelState {
  return {
    status,
    baselineRevisionId,
    message
  }
}

function revokePreviewUrls() {
  Object.values(previewUrlCache.value).forEach((url) => URL.revokeObjectURL(url))
  previewUrlCache.value = {}
}

function cloneMaskRegion(item: MaskRegion): TemplateMaskDraft {
  return {
    id: item.id,
    name: item.name,
    xRatio: item.xRatio,
    yRatio: item.yRatio,
    widthRatio: item.widthRatio,
    heightRatio: item.heightRatio,
    sortOrder: item.sortOrder,
    isNew: false
  }
}

function stripDraftRegion(item: TemplateMaskDraft): MaskRegion {
  return {
    id: item.id,
    name: item.name,
    xRatio: item.xRatio,
    yRatio: item.yRatio,
    widthRatio: item.widthRatio,
    heightRatio: item.heightRatio,
    sortOrder: item.sortOrder
  }
}

function normalizeDraftMaskRegions(items: TemplateMaskDraft[]) {
  return [...items]
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .map((item, index) => ({
      ...item,
      sortOrder: index + 1
    }))
}

function serializeRegions(items: MaskRegion[]) {
  return JSON.stringify(
    [...items]
      .sort((left, right) => left.sortOrder - right.sortOrder)
      .map((item, index) => ({
        id: item.id,
        name: item.name,
        xRatio: Number(item.xRatio.toFixed(4)),
        yRatio: Number(item.yRatio.toFixed(4)),
        widthRatio: Number(item.widthRatio.toFixed(4)),
        heightRatio: Number(item.heightRatio.toFixed(4)),
        sortOrder: index + 1
      }))
  )
}

function hasRegionChanged(currentRegion: MaskRegion, nextRegion: MaskRegion) {
  return (
    currentRegion.name !== nextRegion.name ||
    Number(currentRegion.xRatio.toFixed(4)) !== Number(nextRegion.xRatio.toFixed(4)) ||
    Number(currentRegion.yRatio.toFixed(4)) !== Number(nextRegion.yRatio.toFixed(4)) ||
    Number(currentRegion.widthRatio.toFixed(4)) !== Number(nextRegion.widthRatio.toFixed(4)) ||
    Number(currentRegion.heightRatio.toFixed(4)) !== Number(nextRegion.heightRatio.toFixed(4)) ||
    currentRegion.sortOrder !== nextRegion.sortOrder
  )
}

function replaceDraftMaskRegions(items: TemplateMaskDraft[]) {
  draftMaskRegions.value = normalizeDraftMaskRegions(items)
  if (!draftMaskRegions.value.some((item) => item.id === selectedMaskId.value)) {
    selectedMaskId.value = draftMaskRegions.value[0]?.id ?? null
  }
}

function resetEditorState(template: Template | null) {
  editorMode.value = 'view'
  draftMaskRegions.value = template?.maskRegions.map(cloneMaskRegion) ?? []
  selectedMaskId.value = template?.maskRegions[0]?.id ?? null
}

function resetCreateForm() {
  createForm.templateCode = ''
  createForm.templateName = ''
  createForm.templateType = 'page'
  createForm.matchStrategy = 'template'
  createForm.thresholdValue = 0.95
  createForm.status = 'draft'
  createSourceFile.value = null
  if (createFileInputRef.value) {
    createFileInputRef.value.value = ''
  }
}

function resetEditForm() {
  if (!currentTemplate.value) {
    editForm.templateName = ''
    editForm.templateType = 'page'
    editForm.matchStrategy = 'template'
    editForm.thresholdValue = 0.95
    editForm.status = 'draft'
    return
  }

  editForm.templateName = currentTemplate.value.name
  editForm.templateType = currentTemplate.value.templateType
  editForm.matchStrategy = currentTemplate.value.matchStrategy
  editForm.thresholdValue = currentTemplate.value.thresholdValue
  editForm.status = currentTemplate.value.status
}

function resetBaselineForm() {
  baselineForm.remark = ''
  baselineForm.isCurrent = true
  baselineFile.value = null
  if (baselineFileInputRef.value) {
    baselineFileInputRef.value.value = ''
  }
}

function trimText(value: string) {
  return value.trim()
}

function isThresholdValueValid(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

function buildTemplateFilters(): ListTemplatesParams {
  return {
    keyword: trimText(listFilters.keyword) || undefined,
    status: listFilters.status || undefined,
    templateType: listFilters.templateType || undefined
  }
}

const activeMaskRegions = computed(() => {
  if (editorMode.value === 'edit') {
    return draftMaskRegions.value.map(stripDraftRegion)
  }

  return currentTemplate.value?.maskRegions ?? []
})

const selectedDraftMask = computed(() => {
  return draftMaskRegions.value.find((item) => item.id === selectedMaskId.value) ?? null
})

const selectedMask = computed(() => {
  return activeMaskRegions.value.find((item) => item.id === selectedMaskId.value) ?? null
})

const hasUnsavedChanges = computed(() => {
  if (!currentTemplate.value || editorMode.value !== 'edit') {
    return false
  }

  return (
    serializeRegions(currentTemplate.value.maskRegions) !==
    serializeRegions(draftMaskRegions.value.map(stripDraftRegion))
  )
})

const hasPendingMaskDraft = computed(() => {
  return editorMode.value === 'edit' && hasUnsavedChanges.value
})

const selectedMaskName = computed({
  get: () => selectedDraftMask.value?.name ?? '',
  set: (value: string) => {
    if (editorMode.value !== 'edit' || !selectedDraftMask.value) {
      return
    }

    replaceDraftMaskRegions(
      draftMaskRegions.value.map((item) => {
        if (item.id !== selectedDraftMask.value?.id) {
          return item
        }

        return {
          ...item,
          name: value
        }
      })
    )
  }
})

const createCodeError = computed(() => {
  return trimText(createForm.templateCode) ? '' : '请输入模板编码。'
})

const createNameError = computed(() => {
  return trimText(createForm.templateName) ? '' : '请输入模板名称。'
})

const createThresholdError = computed(() => {
  return isThresholdValueValid(createForm.thresholdValue) ? '' : '请输入 0 ~ 1 的匹配阈值。'
})

const createFileError = computed(() => {
  return createSourceFile.value ? '' : '请先选择原始模板文件。'
})

const editNameError = computed(() => {
  return trimText(editForm.templateName) ? '' : '请输入模板名称。'
})

const editThresholdError = computed(() => {
  return isThresholdValueValid(editForm.thresholdValue) ? '' : '请输入 0 ~ 1 的匹配阈值。'
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

const baselineRevisions = computed<BaselineRevision[]>(() => {
  return currentTemplate.value?.baselineRevisions ?? []
})

const currentBaselineRevision = computed(() => {
  return baselineRevisions.value.find((item) => item.id === selectedBaselineRevisionId.value) ?? null
})

const ocrBlocks = computed<TemplateOcrBlock[]>(() => {
  return ocrSnapshot.value?.blocks ?? []
})

const canTriggerOcr = computed(() => {
  return Boolean(currentTemplate.value && currentBaselineRevision.value)
})

const detailBaselineVersionLabel = computed(() => {
  if (currentBaselineRevision.value) {
    return `v${currentBaselineRevision.value.revisionNo}`
  }

  return currentTemplate.value?.baselineVersion ?? '未设置'
})

const workbenchImageLabel = computed(() => {
  if (!currentBaselineRevision.value) {
    return '当前暂无工作基准图'
  }

  const revisionLabel = `v${currentBaselineRevision.value.revisionNo}`
  const sourceLabel = currentBaselineRevision.value.isCurrent ? '当前基准' : '历史基准'
  return `${revisionLabel} · ${sourceLabel}`
})

const workbenchViewOptions = [
  { label: '原图', value: 'original' },
  { label: 'OCR', value: 'ocr' },
  { label: 'Mask', value: 'mask' },
  { label: '处理后', value: 'processed' }
] as const

const hasActiveFilters = computed(() => {
  const filters = buildTemplateFilters()
  return Boolean(filters.keyword || filters.status || filters.templateType)
})

const listEmptyDescription = computed(() => {
  return hasActiveFilters.value ? '当前筛选条件下暂无模板' : '当前工作空间暂无模板'
})

function blockMaskDraftInterruption(actionLabel: string) {
  if (!hasPendingMaskDraft.value) {
    return false
  }

  ElMessage.warning(`当前 Mask 草稿尚未保存，请先保存或取消后再${actionLabel}。`)
  return true
}

function syncSelectedBaselineRevision(template: Template | null) {
  if (!template || template.baselineRevisions.length === 0) {
    selectedBaselineRevisionId.value = null
    return
  }

  const currentBaseline =
    template.baselineRevisions.find((item) => item.isCurrent) ?? template.baselineRevisions[0]
  selectedBaselineRevisionId.value = currentBaseline.id
}

function resetDerivedWorkbenchState() {
  const baselineRevisionId = currentBaselineRevision.value?.id ?? null
  ocrSnapshot.value = null
  selectedOcrResultId.value = null
  ocrPanelState.value = createIdleOcrState('当前基准版本尚未生成 OCR 结果。', baselineRevisionId)
  processedPreviewState.value = createIdlePreviewState(
    '切换到处理后视图后，将基于当前基准版本和 Mask 重新生成预览。',
    baselineRevisionId
  )
}

async function ensurePreviewUrl(mediaObjectId: number, contentUrl?: string | null) {
  if (previewUrlCache.value[mediaObjectId]) {
    return previewUrlCache.value[mediaObjectId]
  }

  const blob = contentUrl
    ? await requestBlob({
        method: 'get',
        url: contentUrl
      })
    : await getMediaObjectContent(mediaObjectId)
  const objectUrl = URL.createObjectURL(blob)
  previewUrlCache.value = {
    ...previewUrlCache.value,
    [mediaObjectId]: objectUrl
  }
  return objectUrl
}

async function loadWorkbenchImage() {
  if (!currentBaselineRevision.value) {
    baselinePreviewUrl.value = ''
    baselinePreviewError.value = '当前模板暂无可用基准图。'
    baselinePreviewLoading.value = false
    return
  }

  baselinePreviewLoading.value = true
  baselinePreviewError.value = ''

  try {
    baselinePreviewUrl.value = await ensurePreviewUrl(currentBaselineRevision.value.mediaObjectId)
  } catch (error) {
    baselinePreviewUrl.value = ''
    baselinePreviewError.value =
      error instanceof Error ? error.message : '当前基准图加载失败，请稍后重试。'
  } finally {
    baselinePreviewLoading.value = false
  }
}

function buildPreviewMaskPayload() {
  if (editorMode.value !== 'edit') {
    return undefined
  }

  return draftMaskRegions.value.map((item) => ({
    name: item.name,
    xRatio: item.xRatio,
    yRatio: item.yRatio,
    widthRatio: item.widthRatio,
    heightRatio: item.heightRatio,
    sortOrder: item.sortOrder
  }))
}

async function loadPreviewImages() {
  if (!currentTemplate.value || !currentBaselineRevision.value) {
    processedPreviewState.value = createIdlePreviewState('当前基准版本不可用于生成预览。', null)
    return
  }

  processedPreviewState.value = {
    ...createIdlePreviewState('正在生成 Mask 预览图...', currentBaselineRevision.value.id),
    status: 'loading'
  }

  try {
    const preview = await getTemplateProcessedPreview(
      currentTemplate.value.id,
      currentBaselineRevision.value.id,
      buildPreviewMaskPayload()
    )

    processedPreviewState.value = {
      ...preview,
      overlayImageUrl: await ensurePreviewUrl(preview.overlayMediaObjectId ?? 0),
      processedImageUrl: await ensurePreviewUrl(preview.processedMediaObjectId ?? 0),
      message: editorMode.value === 'edit' ? '当前展示的是草稿 Mask 预览结果。' : '当前展示的是正式 Mask 预览结果。'
    }
  } catch (error) {
    processedPreviewState.value = {
      ...createIdlePreviewState(
        error instanceof Error ? error.message : 'Mask 预览生成失败，请稍后重试。',
        currentBaselineRevision.value.id
      ),
      status: 'error'
    }
  }
}

async function loadTemplates(options: { preferredTemplateId?: number | null } = {}) {
  listLoading.value = true
  listError.value = ''

  try {
    const items = await listTemplates(buildTemplateFilters())
    templates.value = items

    if (items.length === 0) {
      selectedTemplateId.value = null
      currentTemplate.value = null
      resetEditorState(null)
      selectedBaselineRevisionId.value = null
      baselinePreviewUrl.value = ''
      baselinePreviewError.value = ''
      resetDerivedWorkbenchState()
      return items
    }

    const preferredTemplateId = options.preferredTemplateId ?? null
    const nextSelectedTemplateId = items.some((item) => item.id === preferredTemplateId)
      ? preferredTemplateId
      : items.some((item) => item.id === selectedTemplateId.value)
        ? selectedTemplateId.value
        : items[0].id

    if (nextSelectedTemplateId !== selectedTemplateId.value) {
      selectedTemplateId.value = nextSelectedTemplateId
    }

    return items
  } catch (error) {
    listError.value = error instanceof Error ? error.message : '模板列表加载失败，请稍后重试。'
    if (templates.value.length === 0) {
      templates.value = []
      selectedTemplateId.value = null
      currentTemplate.value = null
      resetEditorState(null)
      selectedBaselineRevisionId.value = null
      baselinePreviewUrl.value = ''
      baselinePreviewError.value = ''
      resetDerivedWorkbenchState()
    }
    return []
  } finally {
    listLoading.value = false
  }
}

async function loadTemplateDetail(templateId: number) {
  detailLoading.value = true
  detailError.value = ''

  try {
    const detail = await getTemplateDetail(templateId)
    currentTemplate.value = detail
    resetEditorState(detail)
    syncSelectedBaselineRevision(detail)
    resetDerivedWorkbenchState()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '模板详情加载失败，请稍后重试。'
    currentTemplate.value = null
    resetEditorState(null)
    selectedBaselineRevisionId.value = null
    baselinePreviewUrl.value = ''
    baselinePreviewError.value = ''
    resetDerivedWorkbenchState()
  } finally {
    detailLoading.value = false
  }
}

async function reloadCurrentTemplate() {
  if (!selectedTemplateId.value) {
    return
  }

  await loadTemplateDetail(selectedTemplateId.value)
}

function openCreateDialog() {
  if (blockMaskDraftInterruption('新建模板')) {
    return
  }

  resetCreateForm()
  createDialogVisible.value = true
}

function closeCreateDialog() {
  createDialogVisible.value = false
  resetCreateForm()
}

function openEditDialog() {
  if (!currentTemplate.value) {
    return
  }

  if (blockMaskDraftInterruption('编辑模板')) {
    return
  }

  resetEditForm()
  editDialogVisible.value = true
}

function closeEditDialog() {
  editDialogVisible.value = false
  resetEditForm()
}

function openBaselineDialog() {
  if (!currentTemplate.value) {
    return
  }

  if (blockMaskDraftInterruption('新增基准版本')) {
    return
  }

  resetBaselineForm()
  baselineDialogVisible.value = true
}

function closeBaselineDialog() {
  baselineDialogVisible.value = false
  resetBaselineForm()
}

function handleCreateFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  createSourceFile.value = input.files?.[0] ?? null
}

function handleBaselineFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  baselineFile.value = input.files?.[0] ?? null
}

function resolveMediaObjectLabel(mediaObjectId: number) {
  return mediaObjectNameCache.value[mediaObjectId] ?? `媒体对象 #${mediaObjectId}`
}

function handleStartEditing() {
  if (!currentTemplate.value) {
    return
  }

  if (!currentBaselineRevision.value || !baselinePreviewUrl.value) {
    ElMessage.warning('当前模板暂无可编辑的真实基准图，请先选择可用基准版本。')
    return
  }

  draftMaskRegions.value = currentTemplate.value.maskRegions.map(cloneMaskRegion)
  selectedMaskId.value = draftMaskRegions.value[0]?.id ?? null
  editorMode.value = 'edit'
  workbenchViewMode.value = 'mask'
}

function handleCancelEditing() {
  resetEditorState(currentTemplate.value)
  if (workbenchViewMode.value === 'processed' || workbenchViewMode.value === 'mask') {
    void loadPreviewImages()
  }
  ElMessage.info('已取消本次 Mask 编辑。')
}

function handleCanvasRegionsUpdate(items: MaskRegion[]) {
  if (editorMode.value !== 'edit') {
    return
  }

  const existingFlags = new Map(
    draftMaskRegions.value.map((item) => [item.id, Boolean(item.isNew)])
  )

  replaceDraftMaskRegions(
    items.map((item) => ({
      ...item,
      isNew: existingFlags.get(item.id) ?? item.id < 0
    }))
  )
}

function handleAddMaskRegion() {
  if (editorMode.value !== 'edit') {
    return
  }

  const nextId =
    draftMaskRegions.value.reduce((minimumId, item) => Math.min(minimumId, item.id), 0) - 1
  const nextMask: TemplateMaskDraft = {
    id: nextId,
    name: `未命名区域 ${draftMaskRegions.value.length + 1}`,
    xRatio: 0.32,
    yRatio: 0.24,
    widthRatio: 0.2,
    heightRatio: 0.18,
    sortOrder: draftMaskRegions.value.length + 1,
    isNew: true
  }

  replaceDraftMaskRegions([...draftMaskRegions.value, nextMask])
  selectedMaskId.value = nextId
}

function handleDeleteSelectedMask() {
  if (editorMode.value !== 'edit' || !selectedMaskId.value) {
    return
  }

  replaceDraftMaskRegions(
    draftMaskRegions.value.filter((item) => item.id !== selectedMaskId.value)
  )
  ElMessage.success('已从草稿中移除当前 Mask。')
}

function handleMaskRowClick(row: MaskRegion) {
  selectedMaskId.value = row.id
}

function handleSelectWorkbenchViewMode(mode: TemplateWorkbenchViewMode) {
  if (mode === workbenchViewMode.value) {
    if (mode === 'processed' || (mode === 'mask' && editorMode.value !== 'edit')) {
      void loadPreviewImages()
    }
    return
  }

  workbenchViewMode.value = mode
}

function handleSelectBaselineRevision(revisionId: number) {
  if (revisionId === selectedBaselineRevisionId.value) {
    return
  }

  if (blockMaskDraftInterruption('切换基准版本')) {
    return
  }

  selectedBaselineRevisionId.value = revisionId
}

async function loadOcrSnapshot() {
  if (!currentTemplate.value || !currentBaselineRevision.value) {
    ocrSnapshot.value = null
    ocrPanelState.value = createIdleOcrState('当前基准版本尚未生成 OCR 结果。', null)
    return
  }

  try {
    const snapshot = await listTemplateOcrResults(
      currentTemplate.value.id,
      currentBaselineRevision.value.id
    )

    ocrSnapshot.value = snapshot

    if (snapshot.status === 'not_generated') {
      ocrPanelState.value = createIdleOcrState(
        snapshot.errorMessage || '当前基准版本尚未生成 OCR 结果，可手动触发分析。',
        currentBaselineRevision.value.id,
        'not_generated'
      )
      return
    }

    ocrPanelState.value = createIdleOcrState(
      snapshot.status === 'failed'
        ? snapshot.errorMessage || '该基准版本最近一次 OCR 分析失败，可重新触发。'
        : `已加载 OCR 快照，共 ${snapshot.blocks.length} 个识别块。`,
      currentBaselineRevision.value.id,
      snapshot.status === 'failed' ? 'error' : 'ready'
    )
  } catch (error) {
    ocrSnapshot.value = null
    ocrPanelState.value = createIdleOcrState(
      error instanceof Error ? error.message : 'OCR 快照加载失败，请稍后重试。',
      currentBaselineRevision.value?.id ?? null,
      'error'
    )
  }
}

async function handleTriggerOcrAnalysis() {
  if (!currentTemplate.value || !currentBaselineRevision.value) {
    ElMessage.warning('请先选择可用的基准版本。')
    return
  }

  ocrPanelState.value = createIdleOcrState(
    '正在执行 OCR 分析，请稍候...',
    currentBaselineRevision.value.id,
    'loading'
  )

  try {
    const snapshot = await requestTemplateOcrAnalysis(
      currentTemplate.value.id,
      currentBaselineRevision.value.id
    )
    ocrSnapshot.value = snapshot
    ocrPanelState.value = createIdleOcrState(
      snapshot.status === 'failed'
        ? snapshot.errorMessage || 'OCR 分析失败，请稍后重试。'
        : `OCR 分析完成，共识别 ${snapshot.blocks.length} 个结果。`,
      currentBaselineRevision.value.id,
      snapshot.status === 'failed' ? 'error' : 'ready'
    )
    workbenchViewMode.value = 'ocr'
    ElMessage.success('OCR 分析完成。')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'OCR 分析失败，请稍后重试。'
    ocrPanelState.value = createIdleOcrState(
      message,
      currentBaselineRevision.value.id,
      'error'
    )

    if (error instanceof ApiError && error.code === 'TEMPLATE_OCR_ANALYSIS_FAILED') {
      void loadOcrSnapshot()
    }

    ElMessage.error(message)
  }
}

function handleSelectOcrBlock(blockId: string | null) {
  selectedOcrResultId.value = blockId

  if (!ocrSnapshot.value) {
    return
  }

  ocrSnapshot.value = {
    ...ocrSnapshot.value,
    blocks: ocrSnapshot.value.blocks.map((item) => ({
      ...item,
      highlighted: item.id === blockId
    }))
  }
}

function handleConvertOcrResultToMask(result: TemplateOcrBlock) {
  if (editorMode.value !== 'edit') {
    handleStartEditing()
  }

  if (editorMode.value !== 'edit') {
    return
  }

  const nextId =
    draftMaskRegions.value.reduce((minimumId, item) => Math.min(minimumId, item.id), 0) - 1
  const nextMask: TemplateMaskDraft = {
    id: nextId,
    name: trimText(result.text) || `OCR 区域 ${result.orderNo}`,
    xRatio: result.ratioRect.xRatio,
    yRatio: result.ratioRect.yRatio,
    widthRatio: result.ratioRect.widthRatio,
    heightRatio: result.ratioRect.heightRatio,
    sortOrder: draftMaskRegions.value.length + 1,
    isNew: true
  }

  replaceDraftMaskRegions([...draftMaskRegions.value, nextMask])
  selectedMaskId.value = nextId
  selectedOcrResultId.value = result.id
  workbenchViewMode.value = 'mask'
  ElMessage.success('OCR 识别框已转为 Mask 草稿，请继续调整并保存。')
}

function handleSelectTemplate(templateId: number) {
  if (templateId === selectedTemplateId.value) {
    return
  }

  if (blockMaskDraftInterruption('切换模板')) {
    return
  }

  selectedTemplateId.value = templateId
}

async function handleSearchTemplates() {
  if (blockMaskDraftInterruption('查询模板列表')) {
    return
  }

  await loadTemplates()
}

async function handleResetFilters() {
  if (blockMaskDraftInterruption('重置筛选条件')) {
    return
  }

  listFilters.keyword = ''
  listFilters.status = ''
  listFilters.templateType = ''
  await loadTemplates()
}

function formatRatioValue(value: number) {
  return value.toFixed(4)
}

async function handleCreateTemplate() {
  const validationMessage =
    createCodeError.value ||
    createNameError.value ||
    createThresholdError.value ||
    createFileError.value

  if (validationMessage) {
    ElMessage.warning(validationMessage)
    return
  }

  if (!createSourceFile.value || !isThresholdValueValid(createForm.thresholdValue)) {
    ElMessage.warning('请先补齐模板表单与原始文件。')
    return
  }

  createSubmitting.value = true

  try {
    const mediaObject = await createMediaObject(createSourceFile.value, 'template_source')
    mediaObjectNameCache.value = {
      ...mediaObjectNameCache.value,
      [mediaObject.id]: mediaObject.fileName
    }

    const template = await createTemplate({
      code: trimText(createForm.templateCode),
      name: trimText(createForm.templateName),
      templateType: createForm.templateType,
      matchStrategy: createForm.matchStrategy,
      thresholdValue: createForm.thresholdValue,
      status: createForm.status,
      originalMediaObjectId: mediaObject.id
    })

    const items = await loadTemplates({ preferredTemplateId: template.id })
    if (items.some((item) => item.id === template.id)) {
      selectedTemplateId.value = template.id
    }
    closeCreateDialog()
    ElMessage.success('模板已创建。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '创建模板失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    createSubmitting.value = false
  }
}

async function handleEditTemplate() {
  const validationMessage = editNameError.value || editThresholdError.value
  if (validationMessage) {
    ElMessage.warning(validationMessage)
    return
  }

  if (!currentTemplate.value || !selectedTemplateId.value || !isThresholdValueValid(editForm.thresholdValue)) {
    ElMessage.warning('请先补齐模板基础信息。')
    return
  }

  editSubmitting.value = true

  try {
    await updateTemplate(selectedTemplateId.value, {
      name: trimText(editForm.templateName),
      templateType: editForm.templateType,
      matchStrategy: editForm.matchStrategy,
      thresholdValue: editForm.thresholdValue,
      status: editForm.status
    })

    await loadTemplates({ preferredTemplateId: selectedTemplateId.value })
    await reloadCurrentTemplate()
    closeEditDialog()
    ElMessage.success('模板基础信息已更新。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '更新模板失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    editSubmitting.value = false
  }
}

async function handleCreateBaselineRevision() {
  if (!currentTemplate.value || !selectedTemplateId.value || !baselineFile.value) {
    ElMessage.warning('请先选择基准文件。')
    return
  }

  baselineSubmitting.value = true

  try {
    const mediaObject = await createMediaObject(
      baselineFile.value,
      'baseline',
      trimText(baselineForm.remark) || undefined
    )
    mediaObjectNameCache.value = {
      ...mediaObjectNameCache.value,
      [mediaObject.id]: mediaObject.fileName
    }

    await createBaselineRevision(selectedTemplateId.value, {
      mediaObjectId: mediaObject.id,
      sourceType: 'manual',
      remark: trimText(baselineForm.remark) || undefined,
      isCurrent: baselineForm.isCurrent
    })

    await loadTemplates({ preferredTemplateId: selectedTemplateId.value })
    await reloadCurrentTemplate()
    closeBaselineDialog()
    ElMessage.success(baselineSubmitSuccessMessage.value)
  } catch (error) {
    const message = error instanceof Error ? error.message : '新增基准版本失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    baselineSubmitting.value = false
  }
}

async function handleSaveMaskRegions() {
  if (!currentTemplate.value || !selectedTemplateId.value) {
    return
  }

  if (!hasUnsavedChanges.value) {
    editorMode.value = 'view'
    ElMessage.success('Mask 没有变更。')
    return
  }

  const currentRegions = currentTemplate.value.maskRegions
  const nextRegions = draftMaskRegions.value.map(stripDraftRegion)
  const currentMap = new Map(currentRegions.map((item) => [item.id, item]))
  const nextMap = new Map(nextRegions.map((item) => [item.id, item]))

  const deletedRegionIds = currentRegions
    .filter((item) => !nextMap.has(item.id))
    .map((item) => item.id)
  const createdRegions = nextRegions.filter((item) => item.id < 0 || !currentMap.has(item.id))
  const updatedRegions = nextRegions.filter((item) => {
    const currentRegion = currentMap.get(item.id)
    if (!currentRegion) {
      return false
    }

    return hasRegionChanged(currentRegion, item)
  })

  maskSaving.value = true

  try {
    for (const regionId of deletedRegionIds) {
      await deleteMaskRegion(selectedTemplateId.value, regionId)
    }

    for (const region of updatedRegions) {
      await updateMaskRegion(selectedTemplateId.value, region.id, {
        name: region.name,
        xRatio: region.xRatio,
        yRatio: region.yRatio,
        widthRatio: region.widthRatio,
        heightRatio: region.heightRatio,
        sortOrder: region.sortOrder
      })
    }

    for (const region of createdRegions) {
      await createMaskRegion(selectedTemplateId.value, {
        name: region.name,
        xRatio: region.xRatio,
        yRatio: region.yRatio,
        widthRatio: region.widthRatio,
        heightRatio: region.heightRatio,
        sortOrder: region.sortOrder
      })
    }

    await reloadCurrentTemplate()
    if (workbenchViewMode.value === 'processed' || workbenchViewMode.value === 'mask') {
      await loadPreviewImages()
    }
    ElMessage.success('模板 Mask 草稿已保存。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存 Mask 失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    maskSaving.value = false
  }
}

function retryList() {
  if (blockMaskDraftInterruption('重新加载模板列表')) {
    return
  }

  void loadTemplates()
}

function retryDetail() {
  if (!selectedTemplateId.value) {
    return
  }

  void loadTemplateDetail(selectedTemplateId.value)
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasPendingMaskDraft.value) {
    return
  }

  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!hasPendingMaskDraft.value) {
    return true
  }

  ElMessage.warning('当前 Mask 草稿尚未保存，请先保存或取消后再离开当前页面。')
  return false
})

watch(
  selectedTemplateId,
  async (templateId) => {
    if (!templateId) {
      currentTemplate.value = null
      resetEditorState(null)
      selectedBaselineRevisionId.value = null
      baselinePreviewUrl.value = ''
      baselinePreviewError.value = ''
      resetDerivedWorkbenchState()
      return
    }

    await loadTemplateDetail(templateId)
  }
)

watch(
  currentBaselineRevision,
  async () => {
    resetDerivedWorkbenchState()
    await loadWorkbenchImage()
    await loadOcrSnapshot()
    if (workbenchViewMode.value === 'mask' || workbenchViewMode.value === 'processed') {
      await loadPreviewImages()
    }
  }
)

watch(
  workbenchViewMode,
  async (mode) => {
    if (!currentTemplate.value || !currentBaselineRevision.value) {
      return
    }

    if (mode === 'processed') {
      await loadPreviewImages()
    }
  }
)

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  await loadTemplates()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  revokePreviewUrls()
})
</script>

<template>
  <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
    <SectionCard
      description="模板、基准版本与忽略区域命名均对齐 `templates`、`baseline-revisions`、`mask-regions` 资源。"
      title="模板列表"
    >
      <template #action>
        <el-button
          color="#2563eb"
          @click="openCreateDialog"
        >
          新建模板
        </el-button>
      </template>

      <div class="mb-4 space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_140px_140px]">
          <el-input
            v-model="listFilters.keyword"
            clearable
            placeholder="按模板编码或名称筛选"
            @keyup.enter="handleSearchTemplates"
          />
          <el-select
            v-model="listFilters.status"
            clearable
            placeholder="全部状态"
          >
            <el-option
              v-for="item in templateStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="listFilters.templateType"
            clearable
            placeholder="全部类型"
          >
            <el-option
              v-for="item in templateTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>
        <div class="flex justify-end gap-3">
          <el-button plain @click="handleResetFilters">
            重置
          </el-button>
          <el-button color="#2563eb" @click="handleSearchTemplates">
            查询
          </el-button>
        </div>
      </div>

      <div
        v-if="listError"
        class="panel-muted p-5"
      >
        <p class="m-0 text-sm font-medium text-slate-700">
          模板列表加载失败
        </p>
        <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
          {{ listError }}
        </p>
        <el-button
          class="!mt-4"
          plain
          @click="retryList"
        >
          重试
        </el-button>
      </div>

      <div
        v-else-if="listLoading"
        v-loading="true"
        class="min-h-[240px]"
      />

      <el-empty
        v-else-if="templates.length === 0"
        :description="listEmptyDescription"
      >
        <el-button
          color="#2563eb"
          @click="openCreateDialog"
        >
          立即新建模板
        </el-button>
      </el-empty>

      <div
        v-else
        class="space-y-3"
      >
        <button
          v-for="template in templates"
          :key="template.id"
          :class="[
            'w-full rounded-2xl border p-4 text-left transition',
            selectedTemplateId === template.id
              ? 'border-brand-500 bg-brand-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          ]"
          type="button"
          @click="handleSelectTemplate(template.id)"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                {{ template.name }}
              </p>
              <p class="mb-0 mt-2 text-sm text-slate-500">
                {{ template.templateType }} · {{ template.code }}
              </p>
            </div>
            <StatusTag :status="template.status" />
          </div>
          <p class="mb-0 mt-3 text-sm text-slate-400">
            {{ formatDateTime(template.updatedAt) }}
          </p>
        </button>
      </div>
    </SectionCard>

    <div class="space-y-6">
      <SectionCard
        description="模板详情由真实接口驱动，支持基础信息维护、基准版本追加与当前 Mask 持续编辑。"
        title="模板详情"
      >
        <template #action>
          <div
            v-if="currentTemplate && editorMode === 'view'"
            class="flex items-center gap-3"
          >
            <StatusTag :status="currentTemplate.status" />
            <el-button
              plain
              type="primary"
              @click="openEditDialog"
            >
              编辑模板
            </el-button>
            <el-button
              plain
              @click="openBaselineDialog"
            >
              新增基准版本
            </el-button>
            <el-button
              plain
              type="primary"
              @click="handleStartEditing"
            >
              编辑 Mask
            </el-button>
          </div>

          <div
            v-else-if="currentTemplate"
            class="flex items-center gap-3"
          >
            <StatusTag :status="currentTemplate.status" />
            <el-button
              plain
              @click="handleAddMaskRegion"
            >
              新增区域
            </el-button>
            <el-button
              :disabled="!hasUnsavedChanges"
              :loading="maskSaving"
              color="#2563eb"
              @click="handleSaveMaskRegions"
            >
              保存
            </el-button>
            <el-button @click="handleCancelEditing">
              取消
            </el-button>
          </div>
        </template>

        <div
          v-if="detailError"
          class="panel-muted p-5"
        >
          <p class="m-0 text-sm font-medium text-slate-700">
            模板详情加载失败
          </p>
          <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
            {{ detailError }}
          </p>
          <el-button
            class="!mt-4"
            plain
            @click="retryDetail"
          >
            重试
          </el-button>
        </div>

        <div
          v-else-if="detailLoading"
          v-loading="true"
          class="min-h-[320px]"
        />

        <el-empty
          v-else-if="!currentTemplate"
          description="请选择一个模板"
        />

        <div
          v-else
          class="space-y-6"
        >
          <div class="grid grid-cols-4 gap-4">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                模板编码
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.code }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                模板名称
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.name }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                模板类型
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.templateType }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
	              <p class="m-0 text-sm text-slate-500">
	                当前工作基准版本
	              </p>
	              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
	                {{ detailBaselineVersionLabel }}
	              </p>
	            </div>
          </div>

          <div class="grid grid-cols-4 gap-4">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                匹配策略
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.matchStrategy }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                匹配阈值
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.thresholdValue.toFixed(2) }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                创建时间
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ formatDateTime(currentTemplate.createdAt) }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                更新时间
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ formatDateTime(currentTemplate.updatedAt) }}
              </p>
            </div>
          </div>

          <SectionCard
            description="新增基准版本会自动上传媒体对象，并以当前模板上下文追加新的 baseline revision。"
            title="基准版本"
          >
            <template #action>
              <el-select
                :model-value="selectedBaselineRevisionId ?? undefined"
                class="!w-72"
                placeholder="请选择工作基准版本"
                @change="handleSelectBaselineRevision"
              >
                <el-option
                  v-for="revision in baselineRevisions"
                  :key="revision.id"
                  :label="`v${revision.revisionNo} · ${revision.isCurrent ? '当前基准' : '历史基准'}`"
                  :value="revision.id"
                />
              </el-select>
            </template>

            <el-table
              :current-row-key="selectedBaselineRevisionId ?? undefined"
              :data="baselineRevisions"
              empty-text="当前模板尚未记录基准版本"
              highlight-current-row
              row-key="id"
              stripe
              @row-click="handleSelectBaselineRevision($event.id)"
            >
              <el-table-column
                label="版本号"
                min-width="100"
              >
                <template #default="{ row }">
                  v{{ row.revisionNo }}
                </template>
              </el-table-column>
              <el-table-column
                label="来源"
                min-width="120"
                prop="sourceType"
              />
              <el-table-column
                label="当前版本"
                min-width="120"
              >
                <template #default="{ row }">
                  <el-tag :type="row.isCurrent ? 'success' : 'info'" round>
                    {{ row.isCurrent ? '当前版本' : '历史版本' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="备注"
                min-width="200"
              >
                <template #default="{ row }">
                  {{ row.remark || '--' }}
                </template>
              </el-table-column>
              <el-table-column
                label="媒体对象"
                min-width="180"
              >
                <template #default="{ row }">
                  {{ resolveMediaObjectLabel(row.mediaObjectId) }}
                </template>
              </el-table-column>
              <el-table-column
                label="创建时间"
                min-width="180"
              >
                <template #default="{ row }">
                  {{ formatDateTime(row.createdAt) }}
                </template>
              </el-table-column>
            </el-table>
          </SectionCard>

          <SectionCard
            description="模板页已升级为围绕真实基准图工作的前端工作台，当前阶段聚焦真实图片、Mask 编辑与 OCR/预览骨架。"
            title="模板资产工作台"
          >
            <div class="grid grid-cols-[minmax(0,1fr)_360px] gap-6">
              <div class="space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div>
                    <p class="m-0 text-sm font-medium text-slate-700">
                      当前工作基准
                    </p>
                    <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
                      {{
                        currentBaselineRevision
                          ? `当前正在围绕 v${currentBaselineRevision.revisionNo} 进行图片查看、Mask 编辑与后续 OCR 处理。`
                          : '当前模板还没有可用于工作台展示的基准版本。'
                      }}
                    </p>
                  </div>

                  <div class="flex flex-wrap items-center gap-2">
                    <el-button
                      v-for="option in workbenchViewOptions"
                      :key="option.value"
                      :plain="workbenchViewMode !== option.value"
                      :type="workbenchViewMode === option.value ? 'primary' : 'default'"
                      @click="handleSelectWorkbenchViewMode(option.value)"
                    >
                      {{ option.label }}
                    </el-button>
                  </div>
                </div>

                <TemplateCanvas
                  :editable="editorMode === 'edit'"
                  :image-error="baselinePreviewError"
                  :image-label="workbenchImageLabel"
                  :image-loading="baselinePreviewLoading"
                  :image-url="baselinePreviewUrl || null"
                  :ocr-blocks="ocrBlocks"
                  :overlay-image-url="processedPreviewState.overlayImageUrl"
                  :preview-state="workbenchViewMode === 'ocr' ? ocrPanelState : processedPreviewState"
                  :processed-image-url="processedPreviewState.processedImageUrl"
                  :regions="activeMaskRegions"
                  :selected-mask-id="selectedMaskId"
                  :selected-ocr-result-id="selectedOcrResultId"
                  :template-type="currentTemplate.templateType"
                  :view-mode="workbenchViewMode"
                  @update:regions="handleCanvasRegionsUpdate"
                  @update:selected-mask-id="selectedMaskId = $event"
                  @update:selected-ocr-result-id="handleSelectOcrBlock"
                />
              </div>

              <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p
                    v-if="hasPendingMaskDraft"
                    class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700"
                  >
                    当前 Mask 草稿尚未保存。切换模板、切换基准版本、离开页面前，请先保存或取消；同一基准版本内仍可切换视图查看草稿预览。
                  </p>
                  <p class="m-0 text-sm font-medium text-slate-700">
                    当前模式
                  </p>
                  <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
                    {{
                      editorMode === 'edit'
                        ? '编辑模式下可直接基于真实图片拖拽区域、缩放角点，并在右侧维护名称与删除操作。'
                        : '浏览模式下可切换原图、OCR、Mask 与处理后视图，核对工作基准与区域覆盖效果。'
                    }}
                  </p>
                </div>

                <SectionCard
                  description="OCR 结果按 template + baseline revision 唯一快照联调，重复触发会覆盖更新，不展示历史列表。"
                  title="OCR 结果"
                >
                  <template #action>
                    <el-button
                      :disabled="!canTriggerOcr"
                      plain
                      type="primary"
                      @click="handleTriggerOcrAnalysis"
                    >
                      执行 OCR 分析
                    </el-button>
                  </template>

                  <div class="space-y-3">
                    <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
                      {{ ocrPanelState.message }}
                    </div>

                    <div
                      v-if="ocrSnapshot"
                      class="grid grid-cols-2 gap-3 text-sm"
                    >
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">OCR 状态</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ ocrSnapshot.status }}
                        </p>
                      </div>
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">识别引擎</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ ocrSnapshot.engineName }}
                        </p>
                      </div>
                    </div>

                    <el-empty
                      v-if="ocrBlocks.length === 0"
                      description="当前暂无 OCR 结果"
                    />

                    <div
                      v-else
                      class="space-y-3"
                    >
                      <button
                        v-for="result in ocrBlocks"
                        :key="result.id"
                        :class="[
                          'w-full rounded-2xl border p-4 text-left transition',
                          selectedOcrResultId === result.id
                            ? 'border-emerald-400 bg-emerald-50'
                            : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                        ]"
                        type="button"
                        @click="handleSelectOcrBlock(result.id)"
                      >
                        <div class="flex items-start justify-between gap-3">
                          <div>
                            <p class="m-0 text-sm font-semibold text-slate-900">
                              {{ result.orderNo }}. {{ result.text || '未识别文本' }}
                            </p>
                            <p class="mb-0 mt-2 text-xs text-slate-500">
                              置信度 {{ result.confidence.toFixed(2) }}
                            </p>
                          </div>
                          <el-button
                            plain
                            size="small"
                            type="primary"
                            @click.stop="handleConvertOcrResultToMask(result)"
                          >
                            转为 Mask
                          </el-button>
                        </div>
                      </button>
                    </div>
                  </div>
                </SectionCard>

                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div class="mb-4 flex items-center justify-between">
                    <p class="m-0 text-sm font-medium text-slate-700">
                      选中区域
                    </p>
                    <span
                      v-if="selectedMask"
                      class="text-xs text-slate-400"
                    >
                      ID {{ selectedMask.id }}
                    </span>
                  </div>

                  <template v-if="selectedMask">
                    <label class="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-500">
                      区域名称
                    </label>
                    <el-input
                      v-model="selectedMaskName"
                      :disabled="editorMode !== 'edit'"
                      placeholder="请输入区域名称"
                    />

                    <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">横向比例</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ formatRatioValue(selectedMask.xRatio) }}
                        </p>
                      </div>
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">纵向比例</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ formatRatioValue(selectedMask.yRatio) }}
                        </p>
                      </div>
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">宽度比例</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ formatRatioValue(selectedMask.widthRatio) }}
                        </p>
                      </div>
                      <div class="rounded-xl border border-slate-200 bg-white p-3">
                        <p class="m-0 text-slate-500">高度比例</p>
                        <p class="mb-0 mt-2 font-medium text-slate-900">
                          {{ formatRatioValue(selectedMask.heightRatio) }}
                        </p>
                      </div>
                    </div>

                    <el-button
                      v-if="editorMode === 'edit'"
                      class="!mt-4 !w-full"
                      plain
                      type="danger"
                      @click="handleDeleteSelectedMask"
                    >
                      删除当前区域
                    </el-button>
                  </template>

                  <el-empty
                    v-else
                    description="请选择一个 Mask"
                  />
                </div>
              </div>
            </div>

            <el-table
              :current-row-key="selectedMaskId ?? undefined"
              :data="activeMaskRegions"
              class="!mt-6"
              highlight-current-row
              row-key="id"
              @row-click="handleMaskRowClick"
            >
              <el-table-column
                label="名称"
                min-width="200"
                prop="name"
              />
              <el-table-column
                label="横向比例"
                min-width="120"
              >
                <template #default="{ row }">
                  {{ formatRatioValue(row.xRatio) }}
                </template>
              </el-table-column>
              <el-table-column
                label="纵向比例"
                min-width="120"
              >
                <template #default="{ row }">
                  {{ formatRatioValue(row.yRatio) }}
                </template>
              </el-table-column>
              <el-table-column
                label="宽度比例"
                min-width="120"
              >
                <template #default="{ row }">
                  {{ formatRatioValue(row.widthRatio) }}
                </template>
              </el-table-column>
              <el-table-column
                label="高度比例"
                min-width="120"
              >
                <template #default="{ row }">
                  {{ formatRatioValue(row.heightRatio) }}
                </template>
              </el-table-column>
              <el-table-column
                label="排序"
                prop="sortOrder"
                width="120"
              />
            </el-table>
          </SectionCard>
        </div>
      </SectionCard>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      destroy-on-close
      title="新建模板"
      width="560px"
      @closed="resetCreateForm"
    >
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item :error="createCodeError" label="模板编码" required>
          <el-input
            v-model="createForm.templateCode"
            placeholder="请输入模板编码"
          />
        </el-form-item>
        <el-form-item :error="createNameError" label="模板名称" required>
          <el-input
            v-model="createForm.templateName"
            placeholder="请输入模板名称"
          />
        </el-form-item>
        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="模板类型">
            <el-select
              v-model="createForm.templateType"
              class="!w-full"
            >
              <el-option
                v-for="item in templateTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="匹配策略">
            <el-select
              v-model="createForm.matchStrategy"
              class="!w-full"
            >
              <el-option
                v-for="item in matchStrategyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <p class="mb-4 -mt-2 text-xs leading-5 text-slate-400">
          当前联调版本仅支持 `template` 与 `ocr` 两种匹配策略，且只有 `published` 模板可进入执行链路。
        </p>
        <div class="grid grid-cols-2 gap-4">
          <el-form-item :error="createThresholdError" label="匹配阈值" required>
            <el-input-number
              v-model="createForm.thresholdValue"
              :max="1"
              :min="0"
              :precision="2"
              :step="0.01"
              class="!w-full"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select
              v-model="createForm.status"
              class="!w-full"
            >
              <el-option
                v-for="item in templateStatusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item :error="createFileError" label="原始文件" required>
          <input
            ref="createFileInputRef"
            accept="image/*"
            class="block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600"
            type="file"
            @change="handleCreateFileChange"
          >
          <p class="mb-0 mt-2 text-xs text-slate-400">
            {{ createSourceFile?.name ?? '请选择原始模板文件' }}
          </p>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeCreateDialog">
            取消
          </el-button>
          <el-button
            :disabled="!canSubmitCreate"
            :loading="createSubmitting"
            color="#2563eb"
            @click="handleCreateTemplate"
          >
            创建模板
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editDialogVisible"
      destroy-on-close
      title="编辑模板"
      width="560px"
      @closed="resetEditForm"
    >
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item :error="editNameError" label="模板名称" required>
          <el-input
            v-model="editForm.templateName"
            placeholder="请输入模板名称"
          />
        </el-form-item>
        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="模板类型">
            <el-select
              v-model="editForm.templateType"
              class="!w-full"
            >
              <el-option
                v-for="item in templateTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="匹配策略">
            <el-select
              v-model="editForm.matchStrategy"
              class="!w-full"
            >
              <el-option
                v-for="item in matchStrategyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <p class="mb-4 -mt-2 text-xs leading-5 text-slate-400">
          当前联调版本仅支持 `template` 与 `ocr` 两种匹配策略，且只有 `published` 模板可进入执行链路。
        </p>
        <div class="grid grid-cols-2 gap-4">
          <el-form-item :error="editThresholdError" label="匹配阈值" required>
            <el-input-number
              v-model="editForm.thresholdValue"
              :max="1"
              :min="0"
              :precision="2"
              :step="0.01"
              class="!w-full"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select
              v-model="editForm.status"
              class="!w-full"
            >
              <el-option
                v-for="item in templateStatusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeEditDialog">
            取消
          </el-button>
          <el-button
            :disabled="!canSubmitEdit"
            :loading="editSubmitting"
            color="#2563eb"
            @click="handleEditTemplate"
          >
            保存修改
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="baselineDialogVisible"
      destroy-on-close
      title="新增基准版本"
      width="560px"
      @closed="resetBaselineForm"
    >
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="基准文件">
          <input
            ref="baselineFileInputRef"
            accept="image/*"
            class="block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600"
            type="file"
            @change="handleBaselineFileChange"
          >
          <p class="mb-0 mt-2 text-xs text-slate-400">
            {{ baselineFile?.name ?? '请选择新的基准文件' }}
          </p>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="baselineForm.remark"
            placeholder="请输入本次基准版本备注"
          />
        </el-form-item>
        <el-form-item label="设为当前版本">
          <el-checkbox v-model="baselineForm.isCurrent">
            上传后立即设为当前版本
          </el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeBaselineDialog">
            取消
          </el-button>
          <el-button
            :disabled="!canSubmitBaseline"
            :loading="baselineSubmitting"
            color="#2563eb"
            @click="handleCreateBaselineRevision"
          >
            {{ baselineActionLabel }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
