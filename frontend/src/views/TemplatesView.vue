<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError, requestBlob } from '@/api/client'
import BaselineRevisionDialog from '@/components/template/BaselineRevisionDialog.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TemplateBaselineSection from '@/components/template/TemplateBaselineSection.vue'
import TemplateDetailSummary from '@/components/template/TemplateDetailSummary.vue'
import TemplateFormDialog from '@/components/template/TemplateFormDialog.vue'
import TemplateListPanel from '@/components/template/TemplateListPanel.vue'
import TemplateWorkbenchSection from '@/components/template/TemplateWorkbenchSection.vue'
import { WORKSPACE_STORAGE_KEY } from '@/constants/storage'
import {
  isTemplateThresholdValueValid,
  trimTemplateText,
  useTemplateDialogs
} from '@/composables/useTemplateDialogs'
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
import { getWorkspaceExecutionReadiness } from '@/api/modules/workspaces'
import {
  canResolveReadinessByNavigation,
  getReadinessActionLabel,
  getReadinessSuggestion
} from '@/utils/readiness'
import type {
  BaselineRevision,
  ExecutionReadinessIssue,
  MaskRegion,
  Template,
  TemplateOcrBlock,
  TemplateOcrPanelState,
  TemplateEditorMode,
  TemplateMaskDraft,
  TemplateOcrResult,
  TemplatePreviewState,
  TemplateWorkbenchViewMode
} from '@/types/models'

const listLoading = ref(false)
const detailLoading = ref(false)
const maskSaving = ref(false)
const createSubmitting = ref(false)
const editSubmitting = ref(false)
const baselineSubmitting = ref(false)
const listError = ref('')
const detailError = ref('')
const readinessIssuesByTemplateId = ref<Record<number, ExecutionReadinessIssue[]>>({})

const templates = ref<Template[]>([])
const selectedTemplateId = ref<number | null>(null)
const currentTemplate = ref<Template | null>(null)
const editorMode = ref<TemplateEditorMode>('view')
const selectedMaskId = ref<number | null>(null)
const draftMaskRegions = ref<TemplateMaskDraft[]>([])
const mediaObjectNameCache = ref<Record<number, string>>({})

const {
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
  openCreateDialog: openCreateTemplateDialog,
  closeCreateDialog,
  openEditDialog: openEditTemplateDialog,
  closeEditDialog,
  openBaselineDialog: openCreateBaselineDialog,
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
} = useTemplateDialogs(currentTemplate)

const listFilters = reactive({
  keyword: '',
  status: '',
  templateType: ''
})

const workbenchViewMode = ref<TemplateWorkbenchViewMode>('mask')
const selectedBaselineRevisionId = ref<number | null>(null)
const baselinePreviewUrl = ref('')
const baselinePreviewLoading = ref(false)
const baselinePreviewError = ref('')
const previewUrlCache = ref<Record<number, string>>({})
const ocrPanelState = ref<TemplateOcrPanelState>({
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
const route = useRoute()
const router = useRouter()
const highlightedTemplateFocus = ref<'baseline' | 'workbench' | null>(null)

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
  status: TemplateOcrPanelState['status'] = 'idle'
): TemplateOcrPanelState {
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

function buildTemplateFilters(): ListTemplatesParams {
  return {
    keyword: trimTemplateText(listFilters.keyword) || undefined,
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

const currentTemplateReadinessIssues = computed(() => {
  if (!currentTemplate.value) {
    return []
  }
  return readinessIssuesByTemplateId.value[currentTemplate.value.id] ?? []
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
  // @param actionLabel Human-readable action name used in the warning copy.
  // @returns True when the caller should stop because there are unsaved mask edits.
  if (!hasPendingMaskDraft.value) {
    return false
  }

  ElMessage.warning(`当前 Mask 草稿尚未保存，请先保存或取消后再${actionLabel}。`)
  return true
}

function syncSelectedBaselineRevision(template: Template | null) {
  // @param template Current template detail whose baseline list should drive workbench state.
  if (!template || template.baselineRevisions.length === 0) {
    selectedBaselineRevisionId.value = null
    return
  }

  const currentBaseline =
    template.baselineRevisions.find((item) => item.isCurrent) ?? template.baselineRevisions[0]
  selectedBaselineRevisionId.value = currentBaseline.id
}

function resetDerivedWorkbenchState() {
  // Resets OCR and processed-preview state whenever the selected template/baseline changes.
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
  // @param mediaObjectId Media object id used as the cache key for generated object URLs.
  // @param contentUrl Optional direct content URL; falls back to the media-object content API when omitted.
  // @returns A cached or newly created object URL for preview rendering.
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
  // Loads the baseline image currently displayed as the workbench source image.
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
  // @returns The draft mask payload used for preview generation, or undefined in view mode.
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
  // Regenerates processed preview images against the selected baseline and current mask draft state.
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
  // @param options.preferredTemplateId Optional template id that should win when the refreshed list contains it.
  // @returns The latest template list, or an empty array when loading fails.
  listLoading.value = true
  listError.value = ''

  try {
    const items = await listTemplates(buildTemplateFilters())
    templates.value = items
    const workspaceId = Number(localStorage.getItem(WORKSPACE_STORAGE_KEY) ?? 0)
    const readiness = workspaceId
      ? await getWorkspaceExecutionReadiness(workspaceId).catch(() => null)
      : null
    readinessIssuesByTemplateId.value = (readiness?.issues ?? [])
      .filter((issue) => issue.resourceType === 'template' && issue.resourceId !== null)
      .reduce<Record<number, ExecutionReadinessIssue[]>>((acc, issue) => {
        const templateId = issue.resourceId as number
        acc[templateId] = [...(acc[templateId] ?? []), issue]
        return acc
      }, {})

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

    const routeTemplateId = Number(route.query.templateId ?? NaN)
    const preferredTemplateId = options.preferredTemplateId ?? (!Number.isNaN(routeTemplateId) ? routeTemplateId : null)
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
  // @param templateId Template id whose detail, baseline state, and workbench state should be hydrated.
  detailLoading.value = true
  detailError.value = ''

  try {
    const detail = await getTemplateDetail(templateId)
    currentTemplate.value = detail
    resetEditorState(detail)
    syncSelectedBaselineRevision(detail)
    resetDerivedWorkbenchState()
    const focus = route.query.focus
    highlightedTemplateFocus.value = focus === 'baseline' || focus === 'workbench' ? focus : null
    if (highlightedTemplateFocus.value === 'baseline') {
      openBaselineDialog()
    }
    if (highlightedTemplateFocus.value === 'workbench') {
      workbenchViewMode.value = route.query.stepNo ? 'mask' : 'ocr'
    }
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

  openCreateTemplateDialog()
}

function openEditDialog() {
  if (!currentTemplate.value) {
    return
  }

  if (blockMaskDraftInterruption('编辑模板')) {
    return
  }

  openEditTemplateDialog()
}

function openBaselineDialog() {
  if (!currentTemplate.value) {
    return
  }

  if (blockMaskDraftInterruption('新增基准版本')) {
    return
  }

  openCreateBaselineDialog()
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

  const templateId = currentTemplate.value.id
  const baselineRevisionId = currentBaselineRevision.value.id

  ocrPanelState.value = createIdleOcrState(
    '正在执行 OCR 分析，请稍候...',
    baselineRevisionId,
    'loading'
  )

  try {
    const snapshot = await requestTemplateOcrAnalysis(templateId, baselineRevisionId)
    ocrSnapshot.value = snapshot
    ocrPanelState.value = createIdleOcrState(
      snapshot.status === 'failed'
        ? snapshot.errorMessage || 'OCR 分析失败，请稍后重试。'
        : `OCR 分析完成，共识别 ${snapshot.blocks.length} 个结果。`,
      baselineRevisionId,
      snapshot.status === 'failed' ? 'error' : 'ready'
    )
    workbenchViewMode.value = 'ocr'
    ElMessage.success('OCR 分析完成。')
  } catch (error) {
    try {
      const latestSnapshot = await listTemplateOcrResults(templateId, baselineRevisionId)
      if (
        currentTemplate.value?.id === templateId &&
        currentBaselineRevision.value?.id === baselineRevisionId &&
        latestSnapshot.status !== 'not_generated'
      ) {
        ocrSnapshot.value = latestSnapshot
        ocrPanelState.value = createIdleOcrState(
          latestSnapshot.status === 'failed'
            ? latestSnapshot.errorMessage || 'OCR 分析失败，请稍后重试。'
            : `OCR 分析完成，共识别 ${latestSnapshot.blocks.length} 个结果。`,
          baselineRevisionId,
          latestSnapshot.status === 'failed' ? 'error' : 'ready'
        )
        workbenchViewMode.value = 'ocr'
        ElMessage.success('OCR 分析完成。')
        return
      }
    } catch {
      // Ignore snapshot follow-up failures and fall back to the original error state.
    }

    const message = error instanceof Error ? error.message : 'OCR 分析失败，请稍后重试。'
    ocrPanelState.value = createIdleOcrState(message, baselineRevisionId, 'error')

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
    name: trimTemplateText(result.text) || `OCR 区域 ${result.orderNo}`,
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
  void router.replace({ query: { ...route.query, templateId: String(templateId) } })
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

  if (!createSourceFile.value || !isTemplateThresholdValueValid(createForm.thresholdValue)) {
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
      code: trimTemplateText(createForm.templateCode),
      name: trimTemplateText(createForm.templateName),
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

  if (
    !currentTemplate.value ||
    !selectedTemplateId.value ||
    !isTemplateThresholdValueValid(editForm.thresholdValue)
  ) {
    ElMessage.warning('请先补齐模板基础信息。')
    return
  }

  editSubmitting.value = true

  try {
    await updateTemplate(selectedTemplateId.value, {
      name: trimTemplateText(editForm.templateName),
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
      trimTemplateText(baselineForm.remark) || undefined
    )
    mediaObjectNameCache.value = {
      ...mediaObjectNameCache.value,
      [mediaObject.id]: mediaObject.fileName
    }

    await createBaselineRevision(selectedTemplateId.value, {
      mediaObjectId: mediaObject.id,
      sourceType: 'manual',
      remark: trimTemplateText(baselineForm.remark) || undefined,
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
    <TemplateListPanel
      :keyword="listFilters.keyword"
      :list-empty-description="listEmptyDescription"
      :list-error="listError"
      :list-loading="listLoading"
      :readiness-issues-by-template-id="readinessIssuesByTemplateId"
      :selected-template-id="selectedTemplateId"
      :status="listFilters.status"
      :template-type="listFilters.templateType"
      :templates="templates"
      @create="openCreateDialog"
      @reset="handleResetFilters"
      @retry="retryList"
      @search="handleSearchTemplates"
      @select="handleSelectTemplate"
      @update:keyword="listFilters.keyword = $event"
      @update:status="listFilters.status = $event"
      @update:template-type="listFilters.templateType = $event"
    />

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
          <div
            v-if="currentTemplateReadinessIssues.length"
            class="rounded-2xl border border-amber-200 bg-amber-50 p-4"
          >
            <p class="m-0 text-sm font-medium text-amber-900">当前模板会阻塞执行</p>
            <ul class="mb-0 mt-3 list-disc space-y-2 pl-5 text-sm text-amber-800">
              <li
                v-for="issue in currentTemplateReadinessIssues"
                :key="`${issue.code}-${issue.resourceId ?? issue.message}`"
              >
                <span class="block">{{ issue.message }}</span>
                <span class="mt-1 block text-xs text-amber-700">
                  建议操作：{{ getReadinessSuggestion(issue) }}
                </span>
                <span class="mt-2 block">
                  <el-button
                    v-if="canResolveReadinessByNavigation(issue)"
                    plain
                    size="small"
                    @click="issue.code === 'BASELINE_REVISION_REQUIRED' ? openBaselineDialog() : openEditDialog()"
                  >
                    {{ issue.code === 'BASELINE_REVISION_REQUIRED' ? '去补基准' : getReadinessActionLabel(issue) }}
                  </el-button>
                </span>
              </li>
            </ul>
          </div>

          <TemplateDetailSummary
            :current-template="currentTemplate"
            :detail-baseline-version-label="detailBaselineVersionLabel"
          />

          <div
            :class="[
              highlightedTemplateFocus === 'baseline'
                ? 'rounded-3xl border border-amber-200 bg-amber-50 p-2'
                : ''
            ]"
          >
            <TemplateBaselineSection
              :baseline-revisions="baselineRevisions"
              :media-object-name-cache="mediaObjectNameCache"
              :selected-baseline-revision-id="selectedBaselineRevisionId"
              @select="handleSelectBaselineRevision"
            />
          </div>

          <div
            :class="[
              highlightedTemplateFocus === 'workbench'
                ? 'rounded-3xl border border-amber-200 bg-amber-50 p-2'
                : ''
            ]"
          >
            <TemplateWorkbenchSection
              :active-mask-regions="activeMaskRegions"
              :baseline-preview-error="baselinePreviewError"
              :baseline-preview-loading="baselinePreviewLoading"
              :baseline-preview-url="baselinePreviewUrl || null"
              :can-trigger-ocr="canTriggerOcr"
              :current-baseline-revision="currentBaselineRevision"
              :editor-mode="editorMode"
              :has-pending-mask-draft="hasPendingMaskDraft"
              :ocr-blocks="ocrBlocks"
              :ocr-panel-state="ocrPanelState"
              :ocr-snapshot="ocrSnapshot"
              :preview-state="processedPreviewState"
              :selected-mask="selectedMask"
              :selected-mask-id="selectedMaskId"
              :selected-mask-name="selectedMaskName"
              :selected-ocr-result-id="selectedOcrResultId"
              :template-type="currentTemplate.templateType"
              :workbench-image-label="workbenchImageLabel"
              :workbench-view-mode="workbenchViewMode"
              :workbench-view-options="workbenchViewOptions"
              @convert-ocr-result-to-mask="handleConvertOcrResultToMask"
              @delete-selected-mask="handleDeleteSelectedMask"
              @select-mask="selectedMaskId = $event"
              @select-ocr-block="handleSelectOcrBlock"
              @select-view-mode="handleSelectWorkbenchViewMode"
              @trigger-ocr="handleTriggerOcrAnalysis"
              @update:regions="handleCanvasRegionsUpdate"
              @update:selected-mask-name="selectedMaskName = $event"
            />
          </div>
        </div>
      </SectionCard>
    </div>

    <TemplateFormDialog
      :can-submit="canSubmitCreate"
      :code-error="createCodeError"
      :file-error="createFileError"
      :file-name="createSourceFile?.name ?? ''"
      :form="createForm"
      :name-error="createNameError"
      :submitting="createSubmitting"
      :threshold-error="createThresholdError"
      :visible="createDialogVisible"
      mode="create"
      @closed="resetCreateForm"
      @file-change="setCreateSourceFile"
      @submit="handleCreateTemplate"
      @update:visible="createDialogVisible = $event"
    />

    <TemplateFormDialog
      :can-submit="canSubmitEdit"
      :form="editForm"
      :name-error="editNameError"
      :submitting="editSubmitting"
      :threshold-error="editThresholdError"
      :visible="editDialogVisible"
      mode="edit"
      @closed="resetEditForm"
      @submit="handleEditTemplate"
      @update:visible="editDialogVisible = $event"
    />

    <BaselineRevisionDialog
      :action-label="baselineActionLabel"
      :can-submit="canSubmitBaseline"
      :file-name="baselineFile?.name ?? ''"
      :form="baselineForm"
      :submitting="baselineSubmitting"
      :visible="baselineDialogVisible"
      @closed="resetBaselineForm"
      @file-change="setBaselineFile"
      @submit="handleCreateBaselineRevision"
      @update:visible="baselineDialogVisible = $event"
    />
  </div>
</template>
