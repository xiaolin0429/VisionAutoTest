<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TemplateCanvas from '@/components/TemplateCanvas.vue'
import { createMediaObject } from '@/api/modules/mediaObjects'
import {
  createBaselineRevision,
  createMaskRegion,
  createTemplate,
  deleteMaskRegion,
  getTemplateDetail,
  listTemplates,
  updateMaskRegion,
  updateTemplate
} from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import type {
  BaselineRevision,
  MaskRegion,
  Template,
  TemplateEditorMode,
  TemplateMaskDraft
} from '@/types/models'

const templateTypeOptions = [
  { label: '页面模板', value: 'page' },
  { label: '组件模板', value: 'component' },
  { label: '文本区域', value: 'text_region' }
] as const

const matchStrategyOptions = [
  { label: 'Template', value: 'template' },
  { label: 'ORB', value: 'orb' },
  { label: 'OCR', value: 'ocr' },
  { label: 'Mixed', value: 'mixed' }
] as const

const templateStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '启用', value: 'active' },
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

const createForm = reactive({
  templateCode: '',
  templateName: '',
  templateType: 'page',
  matchStrategy: 'template',
  thresholdValue: 0.95,
  status: 'draft'
})

const editForm = reactive({
  templateName: '',
  templateType: 'page',
  matchStrategy: 'template',
  thresholdValue: 0.95,
  status: 'draft'
})

const baselineForm = reactive({
  remark: '',
  isCurrent: true
})

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

async function loadTemplates() {
  listLoading.value = true
  listError.value = ''

  try {
    const items = await listTemplates()
    templates.value = items

    if (items.length === 0) {
      selectedTemplateId.value = null
      currentTemplate.value = null
      resetEditorState(null)
      return
    }

    if (!items.some((item) => item.id === selectedTemplateId.value)) {
      selectedTemplateId.value = items[0].id
    }
  } catch (error) {
    listError.value = error instanceof Error ? error.message : '模板列表加载失败，请稍后重试。'
    if (templates.value.length === 0) {
      templates.value = []
      selectedTemplateId.value = null
      currentTemplate.value = null
      resetEditorState(null)
    }
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
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '模板详情加载失败，请稍后重试。'
    currentTemplate.value = null
    resetEditorState(null)
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

const canSubmitCreate = computed(() => {
  return Boolean(
    createForm.templateCode.trim() &&
      createForm.templateName.trim() &&
      createForm.templateType &&
      createForm.matchStrategy &&
      createForm.status &&
      createSourceFile.value
  )
})

const canSubmitEdit = computed(() => {
  return Boolean(
    currentTemplate.value &&
      editForm.templateName.trim() &&
      editForm.templateType &&
      editForm.matchStrategy &&
      editForm.status
  )
})

const canSubmitBaseline = computed(() => {
  return Boolean(currentTemplate.value && baselineFile.value)
})

function openCreateDialog() {
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

  draftMaskRegions.value = currentTemplate.value.maskRegions.map(cloneMaskRegion)
  selectedMaskId.value = draftMaskRegions.value[0]?.id ?? null
  editorMode.value = 'edit'
}

function handleCancelEditing() {
  resetEditorState(currentTemplate.value)
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

function formatRatioValue(value: number) {
  return value.toFixed(4)
}

async function handleCreateTemplate() {
  if (!canSubmitCreate.value || !createSourceFile.value) {
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
      code: createForm.templateCode.trim(),
      name: createForm.templateName.trim(),
      templateType: createForm.templateType,
      matchStrategy: createForm.matchStrategy,
      thresholdValue: Number(createForm.thresholdValue),
      status: createForm.status,
      originalMediaObjectId: mediaObject.id
    })

    await loadTemplates()
    selectedTemplateId.value = template.id
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
  if (!currentTemplate.value || !selectedTemplateId.value || !canSubmitEdit.value) {
    ElMessage.warning('请先补齐模板基础信息。')
    return
  }

  editSubmitting.value = true

  try {
    await updateTemplate(selectedTemplateId.value, {
      name: editForm.templateName.trim(),
      templateType: editForm.templateType,
      matchStrategy: editForm.matchStrategy,
      thresholdValue: Number(editForm.thresholdValue),
      status: editForm.status
    })

    await loadTemplates()
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
      baselineForm.remark.trim() || undefined
    )
    mediaObjectNameCache.value = {
      ...mediaObjectNameCache.value,
      [mediaObject.id]: mediaObject.fileName
    }

    await createBaselineRevision(selectedTemplateId.value, {
      mediaObjectId: mediaObject.id,
      sourceType: 'manual',
      remark: baselineForm.remark.trim() || undefined,
      isCurrent: true
    })

    await loadTemplates()
    await reloadCurrentTemplate()
    closeBaselineDialog()
    ElMessage.success('基准版本已新增并设为当前版本。')
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
    ElMessage.success('模板 Mask 草稿已保存。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存 Mask 失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    maskSaving.value = false
  }
}

function retryList() {
  void loadTemplates()
}

function retryDetail() {
  if (!selectedTemplateId.value) {
    return
  }

  void loadTemplateDetail(selectedTemplateId.value)
}

watch(
  selectedTemplateId,
  async (templateId) => {
    if (!templateId) {
      currentTemplate.value = null
      resetEditorState(null)
      return
    }

    await loadTemplateDetail(templateId)
  }
)

onMounted(async () => {
  await loadTemplates()
})

const baselineRevisions = computed<BaselineRevision[]>(() => {
  return currentTemplate.value?.baselineRevisions ?? []
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
        description="当前工作空间暂无模板"
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
          @click="selectedTemplateId = template.id"
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
                当前基准版本
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentTemplate.baselineVersion }}
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
            <el-table
              :data="baselineRevisions"
              empty-text="当前模板尚未记录基准版本"
              stripe
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
                  <el-checkbox
                    :model-value="row.isCurrent"
                    disabled
                  />
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
            description="Mask 编辑仍使用相对比例坐标，并在保存后统一重载模板详情。"
            title="Mask 管理"
          >
            <div class="grid grid-cols-[minmax(0,1fr)_320px] gap-6">
              <TemplateCanvas
                :editable="editorMode === 'edit'"
                :image-label="currentTemplate.imageLabel"
                :regions="activeMaskRegions"
                :selected-mask-id="selectedMaskId"
                :template-type="currentTemplate.templateType"
                @update:regions="handleCanvasRegionsUpdate"
                @update:selected-mask-id="selectedMaskId = $event"
              />

              <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p class="m-0 text-sm font-medium text-slate-700">
                    当前模式
                  </p>
                  <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
                    {{
                      editorMode === 'edit'
                        ? '编辑模式下可直接拖拽区域、缩放角点，并在右侧维护名称与删除操作。'
                        : '浏览模式下可点击画布或表格查看某个 Mask 的比例与位置。'
                    }}
                  </p>
                </div>

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
        <el-form-item label="模板编码">
          <el-input
            v-model="createForm.templateCode"
            placeholder="请输入模板编码"
          />
        </el-form-item>
        <el-form-item label="模板名称">
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
        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="匹配阈值">
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
        <el-form-item label="原始文件">
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
        <el-form-item label="模板名称">
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
        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="匹配阈值">
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
          <el-checkbox
            v-model="baselineForm.isCurrent"
            disabled
          >
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
            上传并设为当前版本
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
