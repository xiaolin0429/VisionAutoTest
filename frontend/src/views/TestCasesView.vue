<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listComponents } from '@/api/modules/components'
import {
  createTestCase,
  getTestCaseDetail,
  listTestCases,
  replaceTestCaseSteps,
  updateTestCase
} from '@/api/modules/testCases'
import { listTemplates } from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import {
  LONG_PRESS_BUTTON_OPTIONS,
  NAVIGATE_WAIT_UNTIL_OPTIONS,
  OCR_MATCH_MODE_OPTIONS,
  SCROLL_BEHAVIOR_OPTIONS,
  SCROLL_DIRECTION_OPTIONS,
  SCROLL_TARGET_OPTIONS,
  STEP_TYPE_LABELS,
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
import type { Component, StepType, Template, TestCase } from '@/types/models'

interface StepTemplateOption {
  id: number
  label: string
}

const loading = ref(false)
const savingCase = ref(false)
const savingSteps = ref(false)
const stepSubmitAttempted = ref(false)

const testCases = ref<TestCase[]>([])
const components = ref<Component[]>([])
const templates = ref<Template[]>([])
const selectedCaseId = ref<number | null>(null)
const currentCase = ref<TestCase | null>(null)

const caseDialogVisible = ref(false)
const stepDialogVisible = ref(false)
const caseDialogMode = ref<'create' | 'edit'>('create')

const caseForm = reactive({
  code: '',
  name: '',
  status: 'draft',
  priority: 'p2',
  description: ''
})

const stepDrafts = ref<StepDraft[]>([])

const stepTypeOptions = createStepTypeOptions({ allowComponentCall: true })

const caseStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' }
]

const priorityOptions = [
  { label: 'P0', value: 'p0' },
  { label: 'P1', value: 'p1' },
  { label: 'P2', value: 'p2' },
  { label: 'P3', value: 'p3' }
]

const metrics = computed(() => [
  {
    label: '用例总数',
    value: testCases.value.length,
    hint: '映射 `test-cases` 集合资源。'
  },
  {
    label: '已发布',
    value: testCases.value.filter((item) => item.status === 'published').length,
    hint: '仅已发布用例可进入套件执行链路。'
  },
  {
    label: '当前步骤数',
    value: currentCase.value?.steps.length ?? 0,
    hint: '步骤顺序在保存时会自动重排为连续编号。'
  }
])

const stepValidationErrors = computed(() => {
  return stepDrafts.value.map((step) => validateStepDraft(step))
})

const hasStepValidationErrors = computed(() => {
  return stepValidationErrors.value.some((item) => Object.keys(item).length > 0)
})

function normalizeStepDrafts(items: StepDraft[]) {
  stepDrafts.value = normalizeStepDraftItems(items)
}

function getStepTemplateOptions(step: StepDraft): StepTemplateOption[] {
  if (step.type !== 'template_assert' && step.type !== 'ocr_assert') {
    return []
  }

  const expectedStrategy = step.type === 'template_assert' ? 'template' : 'ocr'
  const options = templates.value
    .filter((item) => item.matchStrategy === expectedStrategy)
    .map((item) => ({
      id: item.id,
      label: formatTemplateOptionLabel(item)
    }))

  if (step.templateId !== null && !options.some((item) => item.id === step.templateId)) {
    const currentTemplate = templates.value.find((item) => item.id === step.templateId)
    if (currentTemplate) {
      options.unshift({
        id: currentTemplate.id,
        label: `${formatTemplateOptionLabel(currentTemplate)} · 当前值不符合 ${expectedStrategy} 策略`
      })
    }
  }

  return options
}

function formatTemplateOptionLabel(template: Template) {
  const baselineLabel =
    template.currentBaselineRevisionId !== null ? `当前基准 ${template.baselineVersion}` : '无当前基准'
  return `${template.name} (#${template.id}) · ${template.status} · ${baselineLabel}`
}

function formatComponentOptionLabel(component: Component) {
  return `${component.name} (#${component.id}) · ${component.status}`
}

function getStepTemplateHint(step: StepDraft) {
  if (step.templateId === null) {
    return ''
  }

  const template = templates.value.find((item) => item.id === step.templateId)
  if (!template) {
    return '当前模板不存在，请重新选择。'
  }

  const messages: string[] = []

  if (step.type === 'template_assert' && template.matchStrategy !== 'template') {
    messages.push('当前模板不是 template 策略。')
  }

  if (step.type === 'ocr_assert' && template.matchStrategy !== 'ocr') {
    messages.push('当前模板不是 ocr 策略。')
  }

  if (template.currentBaselineRevisionId === null) {
    messages.push('当前模板缺少当前基准版本，执行时可能失败。')
  }

  if (template.status !== 'published') {
    messages.push('当前模板未发布，执行前需先发布。')
  }

  return messages.join(' ')
}

function updateStepType(step: StepDraft, nextType: StepType) {
  Object.assign(step, normalizeStepByType(step, nextType))
}

function handleStepTypeModelUpdate(step: StepDraft, value: string | number | boolean) {
  updateStepType(step, value as StepType)
}

function getStepError(index: number, field: keyof StepValidationErrors) {
  return stepValidationErrors.value[index]?.[field] ?? ''
}

function shouldOpenAdvancedPayload(index: number) {
  const draft = stepDrafts.value[index]
  if (!draft) {
    return false
  }

  return shouldOpenAdvancedPayloadDraft(draft)
}

async function loadCaseList() {
  testCases.value = await listTestCases()

  if (!testCases.value.some((item) => item.id === selectedCaseId.value)) {
    selectedCaseId.value = testCases.value[0]?.id ?? null
  }
}

async function loadCaseDetail(testCaseId: number | null) {
  if (!testCaseId) {
    currentCase.value = null
    return
  }

  loading.value = true

  try {
    currentCase.value = await getTestCaseDetail(testCaseId)
  } finally {
    loading.value = false
  }
}

function resetCaseForm() {
  caseForm.code = ''
  caseForm.name = ''
  caseForm.status = 'draft'
  caseForm.priority = 'p2'
  caseForm.description = ''
}

function resetStepDialogState() {
  stepSubmitAttempted.value = false
}

function handleStepDialogClosed() {
  resetStepDialogState()
}

function openCreateCaseDialog() {
  caseDialogMode.value = 'create'
  resetCaseForm()
  caseDialogVisible.value = true
}

function openEditCaseDialog() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  caseDialogMode.value = 'edit'
  caseForm.code = currentCase.value.code
  caseForm.name = currentCase.value.name
  caseForm.status = currentCase.value.status
  caseForm.priority = currentCase.value.priority
  caseForm.description = currentCase.value.description
  caseDialogVisible.value = true
}

async function handleSaveCase() {
  if (!caseForm.name.trim() || (caseDialogMode.value === 'create' && !caseForm.code.trim())) {
    ElMessage.warning('请补齐用例编码与名称。')
    return
  }

  savingCase.value = true

  try {
    if (caseDialogMode.value === 'create') {
      const created = await createTestCase({
        code: caseForm.code.trim(),
        name: caseForm.name.trim(),
        status: caseForm.status,
        priority: caseForm.priority,
        description: caseForm.description.trim()
      })
      selectedCaseId.value = created.id
      ElMessage.success('用例已创建。')
    } else if (currentCase.value) {
      await updateTestCase(currentCase.value.id, {
        name: caseForm.name.trim(),
        status: caseForm.status,
        priority: caseForm.priority,
        description: caseForm.description.trim()
      })
      ElMessage.success('用例已更新。')
    }

    caseDialogVisible.value = false
    await loadCaseList()
    await loadCaseDetail(selectedCaseId.value)
  } finally {
    savingCase.value = false
  }
}

async function publishCurrentCase() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  await updateTestCase(currentCase.value.id, { status: 'published' })
  ElMessage.success('用例已发布。')
  await loadCaseList()
  await loadCaseDetail(currentCase.value.id)
}

function openStepDialog() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  resetStepDialogState()
  normalizeStepDrafts(currentCase.value.steps.map((step) => buildStepDraft(step)))

  if (stepDrafts.value.length === 0) {
    normalizeStepDrafts([createEmptyStepDraft(0)])
  }

  stepDialogVisible.value = true
}

function addStepDraft() {
  normalizeStepDrafts([...stepDrafts.value, createEmptyStepDraft(stepDrafts.value.length)])
}

function removeStepDraft(index: number) {
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

async function handleSaveSteps() {
  if (!currentCase.value) {
    return
  }

  stepSubmitAttempted.value = true

  if (hasStepValidationErrors.value) {
    ElMessage.error('请修正步骤配置后再保存。')
    return
  }

  try {
    const payload = stepDrafts.value.map((step, index) => buildStepWritePayload(step, index))

    savingSteps.value = true
    await replaceTestCaseSteps(currentCase.value.id, payload)
    stepDialogVisible.value = false
    resetStepDialogState()
    ElMessage.success('步骤编排已保存。')
    await loadCaseDetail(currentCase.value.id)
  } catch (error) {
    const message =
      error instanceof ApiError && error.code === 'STEP_CONFIGURATION_INVALID'
        ? error.message
        : '步骤保存失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    savingSteps.value = false
  }
}

watch(
  selectedCaseId,
  async (testCaseId) => {
    await loadCaseDetail(testCaseId)
  },
  { immediate: true }
)

onMounted(async () => {
  loading.value = true

  try {
    const [caseItems, componentItems, templateItems] = await Promise.all([
      listTestCases(),
      listComponents(),
      listTemplates()
    ])

    testCases.value = caseItems
    components.value = componentItems
    templates.value = templateItems
    selectedCaseId.value = caseItems[0]?.id ?? null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
      <SectionCard
        description="对齐 `test-cases` 真实资源，支持新建、编辑与发布。"
        title="用例列表"
      >
        <template #action>
          <el-button
            color="#2563eb"
            @click="openCreateCaseDialog"
          >
            新建用例
          </el-button>
        </template>

        <el-empty
          v-if="testCases.length === 0 && !loading"
          description="当前工作空间暂无用例"
        />

        <div
          v-else
          class="space-y-3"
        >
          <button
            v-for="item in testCases"
            :key="item.id"
            :class="[
              'w-full rounded-2xl border p-4 text-left transition',
              selectedCaseId === item.id
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-200 bg-slate-50 hover:border-slate-300'
            ]"
            type="button"
            @click="selectedCaseId = item.id"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="m-0 text-base font-semibold text-slate-900">
                  {{ item.name }}
                </p>
                <p class="mb-0 mt-2 text-sm text-slate-500">
                  {{ item.code }} · {{ item.priority.toUpperCase() }}
                </p>
              </div>
              <StatusTag :status="item.status" />
            </div>
            <p class="mb-0 mt-3 text-xs text-slate-400">
              {{ formatDateTime(item.updatedAt) }}
            </p>
          </button>
        </div>
      </SectionCard>

      <div class="space-y-6">
        <SectionCard
          description="基础信息与发布状态都通过真实后端接口持久化。"
          title="用例详情"
        >
          <template #action>
            <div
              v-if="currentCase"
              class="flex gap-2"
            >
              <el-button plain @click="openEditCaseDialog">
                编辑信息
              </el-button>
              <el-button
                :disabled="currentCase.status === 'published'"
                color="#2563eb"
                @click="publishCurrentCase"
              >
                发布用例
              </el-button>
            </div>
          </template>

          <div
            v-if="currentCase"
            class="space-y-6"
          >
            <div class="grid grid-cols-4 gap-4">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">用例编码</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ currentCase.code }}</p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">优先级</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                  {{ currentCase.priority.toUpperCase() }}
                </p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">公共组件数</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                  {{ currentCase.componentCount }}
                </p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">状态</p>
                <div class="mt-3">
                  <StatusTag :status="currentCase.status" />
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">用例说明</p>
              <p class="mb-0 mt-3 text-sm leading-6 text-slate-700">
                {{ currentCase.description || '暂无说明' }}
              </p>
            </div>
          </div>

          <el-empty
            v-else
            description="暂无用例数据"
          />
        </SectionCard>

        <SectionCard
          description="步骤顺序从 1 开始连续，默认通过结构化表单完成常用配置。"
          title="步骤编排"
        >
          <template #action>
            <el-button
              :disabled="!currentCase"
              color="#2563eb"
              @click="openStepDialog"
            >
              编排步骤
            </el-button>
          </template>

          <el-table
            v-loading="loading"
            :data="currentCase?.steps ?? []"
            empty-text="当前用例暂无步骤"
            stripe
          >
            <el-table-column label="Step No" prop="stepNo" width="90" />
            <el-table-column label="步骤名称" min-width="220" prop="name" />
            <el-table-column label="类型" min-width="150">
              <template #default="{ row }">
                {{ STEP_TYPE_LABELS[row.type as StepType] }}
              </template>
            </el-table-column>
            <el-table-column label="摘要" min-width="260" prop="target" />
            <el-table-column label="配置说明" min-width="320" prop="note" />
          </el-table>
        </SectionCard>
      </div>
    </div>

    <el-dialog
      v-model="caseDialogVisible"
      :title="caseDialogMode === 'create' ? '新建测试用例' : '编辑测试用例'"
      width="560px"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">用例编码</label>
          <el-input
            v-model="caseForm.code"
            :disabled="caseDialogMode === 'edit'"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">优先级</label>
          <el-select
            v-model="caseForm.priority"
            class="!w-full"
          >
            <el-option
              v-for="option in priorityOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">用例名称</label>
          <el-input v-model="caseForm.name" />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">状态</label>
          <el-select
            v-model="caseForm.status"
            class="!w-full"
          >
            <el-option
              v-for="option in caseStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
          <el-input
            v-model="caseForm.description"
            :rows="4"
            type="textarea"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="caseDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingCase"
            color="#2563eb"
            @click="handleSaveCase"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="stepDialogVisible"
      title="步骤编排"
      top="4vh"
      width="960px"
      @closed="handleStepDialogClosed"
    >
      <div class="mb-4 flex items-start justify-between gap-4">
        <p class="m-0 text-sm leading-6 text-slate-500">
          默认使用结构化表单完成九类常用步骤配置；若有扩展需求，可在每个步骤卡片里展开“高级 payload 配置”。
        </p>
        <el-button plain @click="addStepDraft">
          新增步骤
        </el-button>
      </div>

      <div
        v-if="stepSubmitAttempted && hasStepValidationErrors"
        class="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
      >
        请修正步骤配置后再保存。
      </div>

      <div class="max-h-[65vh] space-y-4 overflow-auto pr-2">
        <div
          v-for="(step, index) in stepDrafts"
          :key="step.id"
          class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
        >
          <div class="mb-4 flex items-center justify-between">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                Step {{ step.stepNo }}
              </p>
              <p class="mb-0 mt-1 text-xs text-slate-400">
                类型：{{ STEP_TYPE_LABELS[step.type] }}，顺序会在保存时自动归一化。
              </p>
            </div>
            <div class="flex gap-2">
              <el-button plain @click="moveStep(index, -1)">
                上移
              </el-button>
              <el-button plain @click="moveStep(index, 1)">
                下移
              </el-button>
              <el-button
                link
                type="danger"
                @click="removeStepDraft(index)"
              >
                删除
              </el-button>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">步骤名称</label>
              <el-input
                v-model="step.name"
                :placeholder="`${STEP_TYPE_LABELS[step.type]} ${step.stepNo}`"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">步骤类型</label>
              <el-select
                :model-value="step.type"
                class="!w-full"
                @update:model-value="handleStepTypeModelUpdate(step, $event)"
              >
                <el-option
                  v-for="option in stepTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>

            <template v-if="step.type === 'wait'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">等待时长(ms)</label>
                <el-input-number
                  v-model="step.waitMs"
                  :min="0"
                  class="!w-full"
                />
                <p
                  v-if="getStepError(index, 'waitMs')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'waitMs') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'click'">
              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input
                  v-model="step.selector"
                  placeholder="例如 [data-testid='submit-button']"
                />
                <p
                  v-if="getStepError(index, 'selector')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'selector') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'navigate'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">URL / 相对路径</label>
                <el-input
                  v-model="step.url"
                  placeholder="例如 /login 或 https://example.com/orders/123"
                />
                <p class="mt-2 text-xs text-slate-500">
                  相对路径将基于环境档案 `base_url` 拼接；绝对 URL 将直接访问。
                </p>
                <p
                  v-if="getStepError(index, 'url')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'url') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">等待策略</label>
                <el-select
                  v-model="step.waitUntil"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in NAVIGATE_WAIT_UNTIL_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'waitUntil')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'waitUntil') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'scroll'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">滑动目标</label>
                <el-select
                  v-model="step.scrollTarget"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in SCROLL_TARGET_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'scrollTarget')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'scrollTarget') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">滑动方向</label>
                <el-select
                  v-model="step.direction"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in SCROLL_DIRECTION_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'direction')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'direction') }}
                </p>
              </div>

              <div
                v-if="step.scrollTarget === 'element'"
                class="col-span-2"
              >
                <label class="mb-2 block text-sm font-medium text-slate-700">目标元素选择器</label>
                <el-input
                  v-model="step.selector"
                  placeholder="例如 .table-container"
                />
                <p
                  v-if="getStepError(index, 'selector')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'selector') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">滑动距离(px)</label>
                <el-input-number
                  v-model="step.distance"
                  :min="1"
                  class="!w-full"
                />
                <p
                  v-if="getStepError(index, 'distance')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'distance') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">滑动行为</label>
                <el-select
                  v-model="step.behavior"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in SCROLL_BEHAVIOR_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'behavior')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'behavior') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'long_press'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input
                  v-model="step.selector"
                  placeholder="例如 [data-testid='card']"
                />
                <p
                  v-if="getStepError(index, 'selector')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'selector') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">长按时长(ms)</label>
                <el-input-number
                  v-model="step.durationMs"
                  :min="1"
                  class="!w-full"
                />
                <p
                  v-if="getStepError(index, 'durationMs')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'durationMs') }}
                </p>
              </div>

              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">按钮类型</label>
                <el-select
                  v-model="step.button"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in LONG_PRESS_BUTTON_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p class="mt-2 text-xs text-slate-500">
                  首期固定支持 `left`，用于覆盖常见 Web UI 与 H5 长按场景。
                </p>
                <p
                  v-if="getStepError(index, 'button')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'button') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'input'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input
                  v-model="step.selector"
                  placeholder="例如 [data-testid='name-input']"
                />
                <p
                  v-if="getStepError(index, 'selector')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'selector') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">输入文本</label>
                <el-input
                  v-model="step.text"
                  placeholder="请输入要填充的内容"
                />
                <p
                  v-if="getStepError(index, 'text')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'text') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'template_assert'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">模板选择</label>
                <el-select
                  v-model="step.templateId"
                  class="!w-full"
                  clearable
                  placeholder="请选择 template 策略模板"
                >
                  <el-option
                    v-for="option in getStepTemplateOptions(step)"
                    :key="option.id"
                    :label="option.label"
                    :value="option.id"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'templateId')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'templateId') }}
                </p>
                <p
                  v-else-if="getStepTemplateHint(step)"
                  class="mt-2 text-xs text-amber-600"
                >
                  {{ getStepTemplateHint(step) }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">阈值(可选)</label>
                <el-input-number
                  v-model="step.threshold"
                  :max="1"
                  :min="0"
                  :precision="2"
                  :step="0.01"
                  :value-on-clear="null"
                  class="!w-full"
                  placeholder="留空则使用模板默认阈值"
                />
                <p
                  v-if="getStepError(index, 'threshold')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'threshold') }}
                </p>
              </div>
            </template>

            <template v-if="step.type === 'ocr_assert'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">
                  OCR 模板(可选)
                </label>
                <el-select
                  v-model="step.templateId"
                  class="!w-full"
                  clearable
                  placeholder="可选，需为 ocr 策略模板"
                >
                  <el-option
                    v-for="option in getStepTemplateOptions(step)"
                    :key="option.id"
                    :label="option.label"
                    :value="option.id"
                  />
                </el-select>
                <p
                  v-if="getStepTemplateHint(step)"
                  class="mt-2 text-xs text-amber-600"
                >
                  {{ getStepTemplateHint(step) }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input
                  v-model="step.selector"
                  placeholder="例如 [data-testid='result-banner']"
                />
                <p
                  v-if="getStepError(index, 'selector')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'selector') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">期望文本</label>
                <el-input
                  v-model="step.expectedText"
                  placeholder="请输入 OCR 期望结果"
                />
                <p
                  v-if="getStepError(index, 'expectedText')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'expectedText') }}
                </p>
              </div>

              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                <el-select
                  v-model="step.matchMode"
                  class="!w-full"
                >
                  <el-option
                    v-for="option in OCR_MATCH_MODE_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'matchMode')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'matchMode') }}
                </p>
              </div>

              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
                <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <el-checkbox v-model="step.caseSensitive">
                    OCR 结果区分大小写
                  </el-checkbox>
                </div>
              </div>
            </template>

            <template v-if="step.type === 'component_call'">
              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">组件选择</label>
                <el-select
                  v-model="step.componentId"
                  class="!w-full"
                  clearable
                  placeholder="请选择组件"
                >
                  <el-option
                    v-for="item in components"
                    :key="item.id"
                    :label="formatComponentOptionLabel(item)"
                    :value="item.id"
                  />
                </el-select>
                <p
                  v-if="getStepError(index, 'componentId')"
                  class="mt-2 text-xs text-rose-600"
                >
                  {{ getStepError(index, 'componentId') }}
                </p>
              </div>
            </template>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">超时时间(ms)</label>
              <el-input-number
                v-model="step.timeoutMs"
                :min="1"
                class="!w-full"
              />
              <p
                v-if="getStepError(index, 'timeoutMs')"
                class="mt-2 text-xs text-rose-600"
              >
                {{ getStepError(index, 'timeoutMs') }}
              </p>
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">重试次数</label>
              <el-input-number
                v-model="step.retryTimes"
                :min="0"
                class="!w-full"
              />
              <p
                v-if="getStepError(index, 'retryTimes')"
                class="mt-2 text-xs text-rose-600"
              >
                {{ getStepError(index, 'retryTimes') }}
              </p>
            </div>

            <div class="col-span-2">
              <details
                :open="shouldOpenAdvancedPayload(index)"
                class="rounded-2xl border border-slate-200 bg-white"
              >
                <summary class="cursor-pointer list-none px-4 py-3 text-sm font-medium text-slate-700">
                  高级 payload 配置
                </summary>
                <div class="border-t border-slate-200 px-4 py-4">
                  <p class="m-0 text-sm leading-6 text-slate-500">
                    这里填写额外 payload JSON。已提供的结构化字段会在保存时自动覆盖同名键。
                  </p>
                  <el-input
                    v-model="step.extraPayloadJson"
                    :rows="5"
                    class="!mt-3"
                    type="textarea"
                  />
                  <p
                    v-if="getStepError(index, 'extraPayloadJson')"
                    class="mt-2 text-xs text-rose-600"
                  >
                    {{ getStepError(index, 'extraPayloadJson') }}
                  </p>
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="stepDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingSteps"
            color="#2563eb"
            @click="handleSaveSteps"
          >
            保存步骤
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
