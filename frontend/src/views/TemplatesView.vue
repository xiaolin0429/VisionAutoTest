<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TemplateCanvas from '@/components/TemplateCanvas.vue'
import {
  createMaskRegion,
  deleteMaskRegion,
  getTemplateDetail,
  listTemplates,
  updateMaskRegion
} from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import type {
  MaskRegion,
  Template,
  TemplateEditorMode,
  TemplateMaskDraft
} from '@/types/models'

const loading = ref(false)
const saving = ref(false)
const templates = ref<Template[]>([])
const selectedTemplateId = ref<number | null>(null)
const currentTemplate = ref<Template | null>(null)
const editorMode = ref<TemplateEditorMode>('view')
const selectedMaskId = ref<number | null>(null)
const draftMaskRegions = ref<TemplateMaskDraft[]>([])

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

async function loadTemplateDetail(templateId: number) {
  loading.value = true
  try {
    const detail = await getTemplateDetail(templateId)
    currentTemplate.value = detail
    resetEditorState(detail)
  } finally {
    loading.value = false
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

onMounted(async () => {
  loading.value = true
  try {
    const items = await listTemplates()
    templates.value = items
    selectedTemplateId.value = items[0]?.id ?? null
  } finally {
    loading.value = false
  }
})

watch(
  selectedTemplateId,
  async (templateId) => {
    if (!templateId) {
      currentTemplate.value = null
      resetEditorState(null)
      return
    }

    await loadTemplateDetail(templateId)
  },
  { immediate: true }
)

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

  saving.value = true
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

    await loadTemplateDetail(selectedTemplateId.value)
    ElMessage.success('模板 Mask 草稿已保存。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存 Mask 失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
    <SectionCard
      description="模板、基准版本与忽略区域命名均对齐 `templates`、`baseline-revisions`、`mask-regions` 资源。"
      title="模板列表"
    >
      <div
        v-loading="loading && templates.length === 0"
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

    <SectionCard
      description="当前模板详情页已切换为 UI 优先 Mock 的 Mask 编辑流，后续可平滑切换到真实写接口。"
      title="模板详情"
    >
      <template #action>
        <div
          v-if="currentTemplate"
          class="flex items-center gap-3"
        >
          <StatusTag :status="currentTemplate.status" />

          <template v-if="editorMode === 'view'">
            <el-button
              plain
              type="primary"
              @click="handleStartEditing"
            >
              编辑 Mask
            </el-button>
          </template>

          <template v-else>
            <el-button
              plain
              @click="handleAddMaskRegion"
            >
              新增区域
            </el-button>
            <el-button
              :disabled="!hasUnsavedChanges"
              :loading="saving"
              color="#2563eb"
              @click="handleSaveMaskRegions"
            >
              保存
            </el-button>
            <el-button @click="handleCancelEditing">
              取消
            </el-button>
          </template>
        </div>
      </template>

      <div
        v-if="currentTemplate"
        v-loading="loading"
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
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              忽略区域数
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ activeMaskRegions.length }}
            </p>
          </div>
        </div>

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
                    <p class="m-0 text-slate-500">x_ratio</p>
                    <p class="mb-0 mt-2 font-medium text-slate-900">
                      {{ formatRatioValue(selectedMask.xRatio) }}
                    </p>
                  </div>
                  <div class="rounded-xl border border-slate-200 bg-white p-3">
                    <p class="m-0 text-slate-500">y_ratio</p>
                    <p class="mb-0 mt-2 font-medium text-slate-900">
                      {{ formatRatioValue(selectedMask.yRatio) }}
                    </p>
                  </div>
                  <div class="rounded-xl border border-slate-200 bg-white p-3">
                    <p class="m-0 text-slate-500">width_ratio</p>
                    <p class="mb-0 mt-2 font-medium text-slate-900">
                      {{ formatRatioValue(selectedMask.widthRatio) }}
                    </p>
                  </div>
                  <div class="rounded-xl border border-slate-200 bg-white p-3">
                    <p class="m-0 text-slate-500">height_ratio</p>
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
            label="x_ratio"
            min-width="120"
          >
            <template #default="{ row }">
              {{ formatRatioValue(row.xRatio) }}
            </template>
          </el-table-column>
          <el-table-column
            label="y_ratio"
            min-width="120"
          >
            <template #default="{ row }">
              {{ formatRatioValue(row.yRatio) }}
            </template>
          </el-table-column>
          <el-table-column
            label="width_ratio"
            min-width="120"
          >
            <template #default="{ row }">
              {{ formatRatioValue(row.widthRatio) }}
            </template>
          </el-table-column>
          <el-table-column
            label="height_ratio"
            min-width="120"
          >
            <template #default="{ row }">
              {{ formatRatioValue(row.heightRatio) }}
            </template>
          </el-table-column>
          <el-table-column
            label="sort_order"
            prop="sortOrder"
            width="120"
          />
        </el-table>
      </div>

      <el-empty
        v-else
        description="暂无模板数据"
      />
    </SectionCard>
  </div>
</template>
