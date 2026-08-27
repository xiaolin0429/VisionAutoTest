<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import StepCanvasEditor from '@/components/step/canvas/StepCanvasEditor.vue'
import {
  getComponentDetail,
  getComponentSteps,
  listComponents
} from '@/api/modules/components'
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
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import type {
  Component,
  ExecutionReadinessIssue,
  Step,
  StepType,
  StepWritePayload,
  Template,
  TestCase
} from '@/types/models'
import type {
  EditableStepPath,
  StepGraphComponentPreview,
  StepStructurePath
} from '@/types/stepGraph'
import { isEditableStepPath } from '@/utils/stepGraph'

interface StepTemplateOption {
  id: number
  label: string
}

const stepEditor = useStepEditor({ allowComponentCall: true })
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()

const loading = ref(false)
const savingCase = ref(false)

const testCases = ref<TestCase[]>([])
const components = ref<Component[]>([])
const templates = ref<Template[]>([])
const selectedCaseId = ref<number | null>(null)
const currentCase = ref<TestCase | null>(null)
const readinessIssuesByCaseId = ref<Record<number, ExecutionReadinessIssue[]>>({})
const highlightedStepNo = ref<number | null>(null)
const stepCanvasVisible = ref(false)
const stepCanvasRef = ref<InstanceType<typeof StepCanvasEditor> | null>(null)
const selectedCanvasPath = ref<StepStructurePath | null>(null)
const componentPreviews = ref<Record<number, StepGraphComponentPreview>>({})
const loadingComponentPreviewIds = new Set<number>()
let handledRepairTargetKey = ''

const currentUserId = computed(
  (): number => authStore.user?.id ?? authStore.currentSession?.user.id ?? 0
)
const currentWorkspaceId = computed(
  (): number => workspaceStore.currentWorkspaceId ?? 0
)

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
  // @param scope Table row scope used to highlight a routed step in the step list.
  return scope.row.stepNo === highlightedStepNo.value ? 'vat-step-highlight' : ''
}

function getStepTemplateOptions(step: StepDraft): StepTemplateOption[] {
  // @param step Current step draft whose type and locator mode determine eligible template options.
  // @returns Template options constrained by assertion strategy or visual locator requirements.
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
  // @param template Template shown in a step editor select option.
  const baselineLabel =
    template.currentBaselineRevisionId !== null ? `当前基准 ${template.baselineVersion}` : '无当前基准'
  return `${template.name} (#${template.id}) · ${template.status} · ${baselineLabel}`
}

function formatComponentOptionLabel(component: Component) {
  return `${component.name} (#${component.id}) · ${component.status}`
}

function getStepTemplateHint(step: StepDraft) {
  // @param step Current step draft whose selected template may be invalid or execution-risky.
  // @returns Human-readable warning text shown under the template selector.
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

async function loadCaseList(): Promise<void> {
  // Loads the case list plus readiness issues, then reconciles current selection with route/query state.
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
  const workspaceId = currentWorkspaceId.value
  const readiness = workspaceId
    ? await getWorkspaceExecutionReadiness(workspaceId).catch(() => null)
    : null
  readinessIssuesByCaseId.value = (readiness?.issues ?? [])
    .filter(
      (issue: ExecutionReadinessIssue): boolean =>
        issue.resourceType === 'test_case' && issue.resourceId !== null
    )
    .reduce<Record<number, ExecutionReadinessIssue[]>>(
      (
        acc: Record<number, ExecutionReadinessIssue[]>,
        issue: ExecutionReadinessIssue
      ): Record<number, ExecutionReadinessIssue[]> => {
        const testCaseId = issue.resourceId as number
        acc[testCaseId] = [...(acc[testCaseId] ?? []), issue]
        return acc
      },
      {}
    )

  if (
    !testCases.value.some(
      (item: TestCase): boolean => item.id === selectedCaseId.value
    )
  ) {
    const routeTestCaseId = Number(route.query.testCaseId ?? NaN)
    selectedCaseId.value = testCases.value.some(
      (item: TestCase): boolean => item.id === routeTestCaseId
    )
      ? routeTestCaseId
      : testCases.value[0]?.id ?? null
  }
}

function resolveTopStepPath(
  steps: TestCase['steps'],
  stepNo: number
): EditableStepPath | null {
  const index = steps.findIndex(
    (step: TestCase['steps'][number]): boolean => step.stepNo === stepNo
  )
  return index >= 0 ? `top:${index}` : null
}

function selectCase(testCaseId: number): void {
  handledRepairTargetKey = ''
  highlightedStepNo.value = null
  selectedCaseId.value = testCaseId
  const { stepNo: _stepNo, ...query } = route.query
  void router.replace({
    query: {
      ...query,
      testCaseId: String(testCaseId)
    }
  })
}

async function loadCaseDetail(testCaseId: number | null): Promise<void> {
  // @param testCaseId Selected test-case id, or null when no case should be shown in the detail panel.
  if (!testCaseId) {
    currentCase.value = null
    highlightedStepNo.value = null
    return
  }

  loading.value = true

  try {
    currentCase.value = await getTestCaseDetail(testCaseId)
    const routeTestCaseId = Number(route.query.testCaseId ?? NaN)
    const routeStepNo = Number(route.query.stepNo ?? NaN)
    const repairPath =
      routeTestCaseId === testCaseId && Number.isInteger(routeStepNo)
        ? resolveTopStepPath(currentCase.value.steps, routeStepNo)
        : null
    highlightedStepNo.value = repairPath ? routeStepNo : null
    if (repairPath) {
      const repairTargetKey = `${testCaseId}:${routeStepNo}`
      if (handledRepairTargetKey !== repairTargetKey) {
        handledRepairTargetKey = repairTargetKey
        openStepCanvas(routeStepNo)
      }
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
  // Creates or updates the current case dialog form depending on the active dialog mode.
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
  // Publishes the currently selected case so it can be referenced by suites and execution flows.
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
  // Clones the selected case, then switches the page selection to the newly created copy.
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

function openStepCanvas(targetStepNo: number | null = null): void {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  stepEditor.initFromSteps(currentCase.value.steps)
  selectedCanvasPath.value =
    targetStepNo === null
      ? null
      : resolveTopStepPath(currentCase.value.steps, targetStepNo)
  stepCanvasVisible.value = true
  void loadComponentPreviews(
    currentCase.value.steps.flatMap(
      (step: Step): number[] =>
        step.type === 'component_call' && step.componentId !== null
          ? [step.componentId]
          : []
    )
  )
}

function mapComponentPreviewStep(step: Step): StepGraphComponentPreview['steps'][number] {
  return {
    name: step.name,
    type: step.type,
    summary: [step.target, step.note].filter(Boolean).join(' · '),
    timeoutMs: step.timeoutMs,
    retryTimes: step.retryTimes
  }
}

async function loadComponentPreview(componentId: number): Promise<void> {
  if (
    loadingComponentPreviewIds.has(componentId) ||
    componentPreviews.value[componentId]?.loadState === 'ready'
  ) {
    return
  }
  loadingComponentPreviewIds.add(componentId)
  const candidate = components.value.find(
    (component: Component): boolean => component.id === componentId
  )
  componentPreviews.value = {
    ...componentPreviews.value,
    [componentId]: {
      componentId,
      name: candidate?.name ?? `组件 #${componentId}`,
      status: candidate?.status ?? 'loading',
      steps: [],
      loadState: 'loading'
    }
  }
  try {
    const [detail, steps] = await Promise.all([
      getComponentDetail(componentId),
      getComponentSteps(componentId)
    ])
    componentPreviews.value = {
      ...componentPreviews.value,
      [componentId]: {
        componentId,
        name: detail.name,
        status: detail.status,
        steps: steps.map(mapComponentPreviewStep),
        loadState: 'ready'
      }
    }
  } catch (error: unknown) {
    componentPreviews.value = {
      ...componentPreviews.value,
      [componentId]: {
        componentId,
        name: candidate?.name ?? `组件 #${componentId}`,
        status: candidate?.status ?? '加载失败',
        steps: [],
        loadState: 'error',
        errorMessage:
          error instanceof Error ? error.message : '组件详情或步骤加载失败。'
      }
    }
  } finally {
    loadingComponentPreviewIds.delete(componentId)
  }
}

async function loadComponentPreviews(componentIds: readonly number[]): Promise<void> {
  const uniqueIds = [...new Set(
    componentIds.filter(
      (componentId: number): boolean =>
        Number.isInteger(componentId) && componentId > 0
    )
  )]
  await Promise.all(
    uniqueIds.map(
      async (componentId: number): Promise<void> =>
        loadComponentPreview(componentId)
    )
  )
}

function openComponentDetail(componentId: number): void {
  stepCanvasVisible.value = false
  void router.push({
    name: 'components',
    query: { componentId: String(componentId) }
  })
}

function handleCanvasDraftsUpdate(drafts: StepDraft[]): void {
  stepEditor.normalizeStepDrafts(drafts)
}

function handleCanvasSelection(path: StepStructurePath | null): void {
  selectedCanvasPath.value = path
}

function handleCanvasReady(): void {
  const path = selectedCanvasPath.value
  if (path && isEditableStepPath(path)) {
    void stepCanvasRef.value?.locate(path)
  }
}

function handleCanvasClosed(): void {
  selectedCanvasPath.value = null
  stepEditor.resetState()
}

async function handleSaveSteps(drafts: StepDraft[]): Promise<void> {
  const testCaseId = currentCase.value?.id
  if (!testCaseId) {
    return
  }

  stepEditor.normalizeStepDrafts(drafts)
  const success = await stepEditor.saveSteps(
    async (payload: StepWritePayload[]): Promise<void> => {
      await replaceTestCaseSteps(testCaseId, payload)
    }
  )
  if (!success) {
    return
  }

  const refreshedCase = await getTestCaseDetail(testCaseId)
  currentCase.value = refreshedCase
  stepEditor.initFromSteps(refreshedCase.steps)
  stepCanvasRef.value?.markSaved(stepEditor.stepDrafts.value)
  stepCanvasVisible.value = false
}

watch(
  selectedCaseId,
  async (testCaseId: number | null): Promise<void> => {
    await loadCaseDetail(testCaseId)
  },
  { immediate: true }
)

onMounted(async (): Promise<void> => {
  loading.value = true

  try {
    const [, componentItems, templateItems] = await Promise.all([
      loadCaseList(),
      listComponents(),
      listTemplates()
    ])

    components.value = componentItems
    templates.value = templateItems
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
            @click="selectCase(item.id)"
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
                      @click="issue.code === 'STEP_CONFIGURATION_INVALID' ? openStepCanvas() : openEditCaseDialog()"
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
              @click="openStepCanvas()"
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

    <StepCanvasEditor
      ref="stepCanvasRef"
      :visible="stepCanvasVisible"
      :user-id="currentUserId"
      :workspace-id="currentWorkspaceId"
      :test-case-id="currentCase?.id ?? 0"
      :title="currentCase?.name ?? '步骤画布'"
      :test-case-code="currentCase?.code ?? ''"
      :step-drafts="stepEditor.stepDrafts.value"
      :component-previews="componentPreviews"
      :selected-path="selectedCanvasPath"
      :saving="stepEditor.savingSteps.value"
      :status-message="stepEditor.stepSaveError.value?.message ?? ''"
      :templates="templates"
      :components="components"
      :allow-component-call="true"
      :validate-step-fn="stepEditor.validateStep"
      :get-step-template-options-fn="getStepTemplateOptions"
      :get-step-template-hint-fn="getStepTemplateHint"
      :format-component-option-label-fn="formatComponentOptionLabel"
      @update:visible="stepCanvasVisible = $event"
      @update:selected-path="handleCanvasSelection"
      @update:step-drafts="handleCanvasDraftsUpdate"
      @save="handleSaveSteps"
      @closed="handleCanvasClosed"
      @open-component="openComponentDetail"
      @ready="handleCanvasReady"
      @request-component-previews="loadComponentPreviews"
    />
  </div>
</template>

<style scoped>
:deep(.vat-step-highlight) {
  --el-table-tr-bg-color: #fef3c7;
}
</style>
