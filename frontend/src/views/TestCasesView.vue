<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import StepEditorDialog from '@/components/step/StepEditorDialog.vue'
import { WORKSPACE_STORAGE_KEY } from '@/constants/storage'
import { listComponents } from '@/api/modules/components'
import {
  cloneTestCase,
  createTestCase,
  getTestCaseDetail,
  listTestCases,
  replaceTestCaseSteps,
  updateTestCase
} from '@/api/modules/testCases'
import { getWorkspaceExecutionReadiness } from '@/api/modules/workspaces'
import { listTemplates } from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import {
  canResolveReadinessByNavigation,
  getReadinessActionLabel,
  getReadinessSuggestion
} from '@/utils/readiness'
import { STEP_TYPE_LABELS, type StepDraft } from '@/utils/steps'
import { useStepEditor } from '@/composables/useStepEditor'
import type { Component, ExecutionReadinessIssue, StepType, Template, TestCase } from '@/types/models'

interface StepTemplateOption {
  id: number
  label: string
}

const stepEditor = useStepEditor({ allowComponentCall: true })
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const savingCase = ref(false)

const testCases = ref<TestCase[]>([])
const components = ref<Component[]>([])
const templates = ref<Template[]>([])
const selectedCaseId = ref<number | null>(null)
const currentCase = ref<TestCase | null>(null)
const readinessIssuesByCaseId = ref<Record<number, ExecutionReadinessIssue[]>>({})
const highlightedStepNo = ref<number | null>(null)

const searchKeyword = ref('')
const filterStatus = ref('')
let searchTimer: number | null = null

const filterStatusOptions = [
  { label: '全部', value: '' },
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' }
]

function handleFilterChange() {
  void loadCaseList()
}

function handleSearchInput() {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer)
  }
  searchTimer = window.setTimeout(() => {
    void loadCaseList()
  }, 300)
}

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

const currentCaseReadinessIssues = computed(() => {
  if (!currentCase.value) {
    return []
  }
  return readinessIssuesByCaseId.value[currentCase.value.id] ?? []
})

function resolveStepRowClassName(scope: { row: { stepNo: number } }) {
  return scope.row.stepNo === highlightedStepNo.value ? 'vat-step-highlight' : ''
}

function getStepTemplateOptions(step: StepDraft): StepTemplateOption[] {
  const usesVisualLocator =
    (step.type === 'click' || step.type === 'input' || step.type === 'scroll' || step.type === 'long_press') &&
    step.locator === 'visual'

  if (step.type !== 'template_assert' && step.type !== 'ocr_assert' && !usesVisualLocator) {
    return []
  }

  const expectedStrategy = step.type === 'ocr_assert' ? 'ocr' : 'template'
  const currentTemplateId = usesVisualLocator ? step.visualTemplateId : step.templateId
  const options = templates.value
    .filter((item) => item.matchStrategy === expectedStrategy)
    .map((item) => ({
      id: item.id,
      label: formatTemplateOptionLabel(item)
    }))

  if (currentTemplateId !== null && !options.some((item) => item.id === currentTemplateId)) {
    const currentTemplate = templates.value.find((item) => item.id === currentTemplateId)
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
  const usesVisualLocator =
    (step.type === 'click' || step.type === 'input' || step.type === 'scroll' || step.type === 'long_press') &&
    step.locator === 'visual'
  const currentTemplateId = usesVisualLocator ? step.visualTemplateId : step.templateId

  if (currentTemplateId === null) {
    return ''
  }

  const template = templates.value.find((item) => item.id === currentTemplateId)
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

  if (usesVisualLocator && template.matchStrategy !== 'template') {
    messages.push('视觉模板定位要求模板使用 template 策略。')
  }

  if (template.currentBaselineRevisionId === null) {
    messages.push('当前模板缺少当前基准版本，执行时可能失败。')
  }

  if (template.status !== 'published') {
    messages.push('当前模板未发布，执行前需先发布。')
  }

  return messages.join(' ')
}

async function loadCaseList() {
  const options: { keyword?: string; status?: string } = {}
  if (searchKeyword.value.trim()) {
    options.keyword = searchKeyword.value.trim()
  }
  if (filterStatus.value) {
    options.status = filterStatus.value
  }

  testCases.value = await listTestCases(
    Object.keys(options).length > 0 ? options : undefined
  )
  const workspaceId = Number(localStorage.getItem(WORKSPACE_STORAGE_KEY) ?? 0)
  const readiness = workspaceId
    ? await getWorkspaceExecutionReadiness(workspaceId).catch(() => null)
    : null
  readinessIssuesByCaseId.value = (readiness?.issues ?? [])
    .filter((issue) => issue.resourceType === 'test_case' && issue.resourceId !== null)
    .reduce<Record<number, ExecutionReadinessIssue[]>>((acc, issue) => {
      const testCaseId = issue.resourceId as number
      acc[testCaseId] = [...(acc[testCaseId] ?? []), issue]
      return acc
    }, {})

  if (!testCases.value.some((item) => item.id === selectedCaseId.value)) {
    const routeTestCaseId = Number(route.query.testCaseId ?? NaN)
    selectedCaseId.value = testCases.value.some((item) => item.id === routeTestCaseId)
      ? routeTestCaseId
      : testCases.value[0]?.id ?? null
  }
}

async function loadCaseDetail(testCaseId: number | null) {
  if (!testCaseId) {
    currentCase.value = null
    highlightedStepNo.value = null
    return
  }

  loading.value = true

  try {
    currentCase.value = await getTestCaseDetail(testCaseId)
    const routeStepNo = Number(route.query.stepNo ?? NaN)
    highlightedStepNo.value = Number.isNaN(routeStepNo) ? null : routeStepNo
    if (
      highlightedStepNo.value !== null &&
      currentCase.value.steps.some((step) => step.stepNo === highlightedStepNo.value)
    ) {
      void router.replace({ query: { ...route.query, testCaseId: String(testCaseId) } })
      openStepDialog()
    }
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

async function handleCloneCase() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  try {
    const cloned = await cloneTestCase(currentCase.value.id)
    selectedCaseId.value = cloned.id
    ElMessage.success('用例已克隆。')
    await loadCaseList()
    await loadCaseDetail(cloned.id)
  } catch {
    ElMessage.error('克隆失败，请重试。')
  }
}

function openStepDialog() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  stepEditor.initFromSteps(currentCase.value.steps)
  stepDialogVisible.value = true
}

async function handleSaveSteps() {
  if (!currentCase.value) return
  const success = await stepEditor.saveSteps(async (payload) => {
    await replaceTestCaseSteps(currentCase.value!.id, payload)
  })
  if (success) {
    stepDialogVisible.value = false
    await loadCaseDetail(currentCase.value.id)
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

        <div class="mb-3 space-y-2">
          <el-input
            v-model="searchKeyword"
            clearable
            placeholder="搜索编码或名称"
            @input="handleSearchInput"
            @clear="handleFilterChange"
          />
          <el-select
            v-model="filterStatus"
            class="!w-full"
            placeholder="按状态筛选"
            @change="handleFilterChange"
          >
            <el-option
              v-for="option in filterStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>

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
            @click="selectedCaseId = item.id; router.replace({ query: { ...route.query, testCaseId: String(item.id) } })"
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
            <p
              v-if="readinessIssuesByCaseId[item.id]?.length"
              class="mb-0 mt-2 text-xs text-amber-700"
            >
              {{ readinessIssuesByCaseId[item.id][0]?.message }}
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
              <el-button plain @click="handleCloneCase">
                克隆
              </el-button>
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
            <div
              v-if="currentCaseReadinessIssues.length"
              class="rounded-2xl border border-amber-200 bg-amber-50 p-4"
            >
              <p class="m-0 text-sm font-medium text-amber-900">当前用例会阻塞执行</p>
              <ul class="mb-0 mt-3 list-disc space-y-2 pl-5 text-sm text-amber-800">
                <li
                  v-for="issue in currentCaseReadinessIssues"
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
                      @click="issue.code === 'STEP_CONFIGURATION_INVALID' ? openStepDialog() : openEditCaseDialog()"
                    >
                      {{ issue.code === 'STEP_CONFIGURATION_INVALID' ? '去编排步骤' : getReadinessActionLabel(issue) }}
                    </el-button>
                  </span>
                </li>
              </ul>
            </div>

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
              :row-class-name="resolveStepRowClassName"
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

    <StepEditorDialog
      :visible="stepDialogVisible"
      :step-drafts="stepEditor.stepDrafts.value"
      :saving-steps="stepEditor.savingSteps.value"
      :step-submit-attempted="stepEditor.stepSubmitAttempted.value"
      :has-step-validation-errors="stepEditor.hasStepValidationErrors.value"
      :step-type-options="stepEditor.stepTypeOptions"
      :templates="templates"
      :components="components"
      :allow-component-call="true"
      :get-step-error-fn="stepEditor.getStepError"
      :should-open-advanced-payload-fn="stepEditor.shouldOpenAdvancedPayload"
      :get-step-template-options-fn="getStepTemplateOptions"
      :get-step-template-hint-fn="getStepTemplateHint"
      :format-component-option-label-fn="formatComponentOptionLabel"
      @update:visible="stepDialogVisible = $event"
      @add-step="stepEditor.addStep()"
      @remove-step="stepEditor.removeStep($event)"
      @move-step="(index, direction) => stepEditor.moveStep(index, direction)"
      @update-step-type="(step, value) => stepEditor.handleStepTypeModelUpdate(step, value)"
      @save="handleSaveSteps"
      @closed="stepEditor.resetState()"
    />
  </div>
</template>

<style scoped>
:deep(.vat-step-highlight) {
  --el-table-tr-bg-color: #fef3c7;
}
</style>
