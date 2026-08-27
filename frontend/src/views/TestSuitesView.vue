<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import SuiteCaseDialog from '@/components/suite/SuiteCaseDialog.vue'
import SuiteFormDialog from '@/components/suite/SuiteFormDialog.vue'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { listTestCases } from '@/api/modules/testCases'
import {
  createTestSuite,
  getTestSuiteExecutionReadiness,
  getTestSuiteDetail,
  listTestSuites,
  replaceSuiteCases,
  updateTestSuite
} from '@/api/modules/testSuites'
import {
  buildReadinessNavigation,
  canResolveReadinessByNavigation,
  getReadinessActionLabel,
  getReadinessSuggestion,
  readinessIssuesFromErrorDetails,
  type ExecutionGateState
} from '@/utils/readiness'
import { createTestRun } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type {
  DeviceProfile,
  EnvironmentProfile,
  ExecutionReadinessSummary,
  SuiteCaseWritePayload,
  TestCase,
  TestSuite
} from '@/types/models'

interface SuiteCaseDraft {
  testCaseId: number
  name: string
  status: string
  orderNo: number
}

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const savingSuite = ref(false)
const savingCases = ref(false)
const gateState = ref<ExecutionGateState>('idle')
let readinessRequestId = 0

const suites = ref<TestSuite[]>([])
const testCases = ref<TestCase[]>([])
const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])

const selectedSuiteId = ref<number | null>(null)
const currentSuite = ref<TestSuite | null>(null)
const readinessSummary = ref<ExecutionReadinessSummary | null>(null)

const suiteDialogVisible = ref(false)
const caseDialogVisible = ref(false)
const suiteDialogMode = ref<'create' | 'edit'>('create')

const suiteForm = reactive({
  code: '',
  name: '',
  status: 'draft',
  description: ''
})

const selectedCaseToAdd = ref<number | null>(null)
const suiteCaseDrafts = ref<SuiteCaseDraft[]>([])

const runForm = reactive({
  testSuiteId: 0,
  environmentProfileId: 0,
  deviceProfileId: null as number | null
})

const suiteStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '归档', value: 'archived' }
]

const readinessIssues = computed(() => readinessSummary.value?.issues ?? [])
const hasBlockingIssues = computed(() => readinessIssues.value.length > 0)
const hasSuiteSelected = computed(() => currentSuite.value !== null)
const primaryReadinessMessage = computed(() => readinessIssues.value[0]?.message ?? '')
const readinessLoading = computed(() => gateState.value === 'checking')

const availableCasesToAdd = computed(() => {
  const selectedIds = new Set(suiteCaseDrafts.value.map((item) => item.testCaseId))
  return testCases.value.filter((item) => !selectedIds.has(item.id))
})

const canRunSuite = computed(() => {
  return Boolean(
    hasSuiteSelected.value &&
      !readinessLoading.value &&
      !hasBlockingIssues.value &&
      gateState.value === 'ready' &&
      runForm.testSuiteId &&
      runForm.environmentProfileId
  )
})

function normalizeSuiteCases(items: SuiteCaseDraft[]) {
  // @param items Suite-case drafts in arbitrary order before the dialog rewrites them into continuous order numbers.
  suiteCaseDrafts.value = items.map((item, index) => ({
    ...item,
    orderNo: index + 1
  }))
}

function formatRunCreationError(error: unknown) {
  // @param error Unknown request error returned by the create-run flow.
  // @returns User-facing error text mapped from known backend execution-readiness codes.
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : '创建执行批次失败，请稍后重试。'
  }

  const errorMessageMap: Record<string, string> = {
    ENVIRONMENT_BASE_URL_INVALID: '执行环境地址无效，请填写包含 http:// 或 https:// 的完整地址。',
    DEVICE_PROFILE_INVALID: '设备档案不可用于本次执行，请检查设备配置。',
    TEST_SUITE_NOT_ACTIVE: '套件未激活，无法执行。',
    PUBLISHED_VERSION_REQUIRED: '存在未发布的用例或组件，请先发布。',
    TEST_SUITE_EMPTY: '套件为空，无法执行。',
    BASELINE_REVISION_REQUIRED: '存在缺少当前基准版本的模板，请先补齐。',
    STEP_CONFIGURATION_INVALID: '存在模板策略与步骤类型不兼容的配置，请先修正。',
    IDEMPOTENCY_KEY_CONFLICT: '请勿重复触发相同执行请求。',
    WORKSPACE_ID_REQUIRED: '当前工作空间上下文缺失，请重新选择工作空间。',
    WORKSPACE_FORBIDDEN: '当前用户没有该工作空间权限。'
  }

  return errorMessageMap[error.code] ?? error.message
}

async function inspectSuiteReadiness() {
  if (!runForm.testSuiteId || !runForm.environmentProfileId) {
    readinessRequestId += 1
    readinessSummary.value = null
    gateState.value = 'idle'
    return
  }

  const requestId = ++readinessRequestId
  gateState.value = 'checking'
  readinessSummary.value = null

  try {
    const summary = await getTestSuiteExecutionReadiness(runForm.testSuiteId, {
      environmentProfileId: runForm.environmentProfileId,
      deviceProfileId: runForm.deviceProfileId
    })
    if (requestId !== readinessRequestId) return
    readinessSummary.value = summary
    gateState.value = summary.status === 'ready' ? 'ready' : 'blocked'
  } catch (error) {
    if (requestId !== readinessRequestId) return
    const suite = suites.value.find((item) => item.id === runForm.testSuiteId)
    readinessSummary.value = {
      scope: 'execution_selection',
      status: 'blocked',
      workspaceId: 0,
      testSuiteId: runForm.testSuiteId,
      environmentProfileId: runForm.environmentProfileId,
      deviceProfileId: runForm.deviceProfileId,
      activeEnvironmentCount: 0,
      activeTestSuiteCount: 0,
      blockingIssueCount: 1,
      issues: [
        {
          code: 'READINESS_LOAD_FAILED',
          message: error instanceof Error ? error.message : '执行门禁检查失败，请稍后重试。',
          resourceType: 'test_suite',
          resourceId: suite?.id ?? runForm.testSuiteId,
          resourceName: suite?.name ?? '',
          routePath: null,
          stepNo: null
        }
      ]
    }
    gateState.value = 'check_failed'
  }
}

function navigateReadinessIssue(issue: ExecutionReadinessSummary['issues'][number]) {
  const target = buildReadinessNavigation(issue)
  if (target) void router.push(target)
}

async function loadPageData() {
  // Loads suites, candidate cases, environments, and devices in parallel for the suite management page.
  loading.value = true

  try {
    const [suiteItems, caseItems, environmentItems, deviceItems] = await Promise.all([
      listTestSuites(),
      listTestCases(),
      listEnvironmentProfiles(),
      listDeviceProfiles()
    ])

    suites.value = suiteItems
    testCases.value = caseItems
    environmentProfiles.value = environmentItems
    deviceProfiles.value = deviceItems

    if (!suiteItems.some((item) => item.id === selectedSuiteId.value)) {
      selectedSuiteId.value = suiteItems[0]?.id ?? null
    }

    if (!runForm.environmentProfileId) {
      runForm.environmentProfileId = environmentItems[0]?.id ?? 0
    }

    if (runForm.deviceProfileId === null) {
      runForm.deviceProfileId = deviceItems[0]?.id ?? null
    }
  } finally {
    loading.value = false
  }
}

function resetSuiteForm() {
  suiteForm.code = ''
  suiteForm.name = ''
  suiteForm.status = 'draft'
  suiteForm.description = ''
}

function openCreateSuiteDialog() {
  suiteDialogMode.value = 'create'
  resetSuiteForm()
  suiteDialogVisible.value = true
}

function openEditSuiteDialog() {
  if (!currentSuite.value) {
    ElMessage.warning('请先选择一个套件。')
    return
  }

  suiteDialogMode.value = 'edit'
  suiteForm.code = currentSuite.value.code
  suiteForm.name = currentSuite.value.name
  suiteForm.status = currentSuite.value.status
  suiteForm.description = currentSuite.value.description
  suiteDialogVisible.value = true
}

async function handleSaveSuite() {
  // Creates or updates the suite dialog form depending on the active dialog mode.
  if (!suiteForm.name.trim() || (suiteDialogMode.value === 'create' && !suiteForm.code.trim())) {
    ElMessage.warning('请补齐套件编码与名称。')
    return
  }

  savingSuite.value = true

  try {
    if (suiteDialogMode.value === 'create') {
      const created = await createTestSuite({
        code: suiteForm.code.trim(),
        name: suiteForm.name.trim(),
        status: suiteForm.status,
        description: suiteForm.description.trim()
      })
      selectedSuiteId.value = created.id
      ElMessage.success('套件已创建。')
    } else if (currentSuite.value) {
      await updateTestSuite(currentSuite.value.id, {
        name: suiteForm.name.trim(),
        status: suiteForm.status,
        description: suiteForm.description.trim()
      })
      ElMessage.success('套件已更新。')
    }

    suiteDialogVisible.value = false
    await loadPageData()
    await loadSuiteDetail(selectedSuiteId.value)
  } finally {
    savingSuite.value = false
  }
}

async function activateCurrentSuite() {
  if (!currentSuite.value) {
    ElMessage.warning('请先选择一个套件。')
    return
  }

  await updateTestSuite(currentSuite.value.id, { status: 'active' })
  ElMessage.success('套件已激活。')
  await loadPageData()
  await loadSuiteDetail(currentSuite.value.id)
}

function openCaseDialog() {
  if (!currentSuite.value) {
    ElMessage.warning('请先选择一个套件。')
    return
  }

  selectedCaseToAdd.value = null
  normalizeSuiteCases(
    currentSuite.value.cases.map((item) => ({
      testCaseId: item.testCaseId,
      name: item.name,
      status: item.status,
      orderNo: item.orderNo
    }))
  )
  caseDialogVisible.value = true
}

function addSuiteCase() {
  // Adds the currently selected case into the suite draft list and normalizes the order numbers.
  if (!selectedCaseToAdd.value) {
    ElMessage.warning('请先选择要加入套件的用例。')
    return
  }

  const testCase = testCases.value.find((item) => item.id === selectedCaseToAdd.value)
  if (!testCase) {
    return
  }

  normalizeSuiteCases([
    ...suiteCaseDrafts.value,
    {
      testCaseId: testCase.id,
      name: testCase.name,
      status: testCase.status,
      orderNo: suiteCaseDrafts.value.length + 1
    }
  ])
  selectedCaseToAdd.value = null
}

function removeSuiteCase(index: number) {
  normalizeSuiteCases(suiteCaseDrafts.value.filter((_, currentIndex) => currentIndex !== index))
}

function moveSuiteCase(index: number, direction: -1 | 1) {
  // @param index Current suite-case row index.
  // @param direction Relative move direction: -1 for up, 1 for down.
  const nextIndex = index + direction
  if (nextIndex < 0 || nextIndex >= suiteCaseDrafts.value.length) {
    return
  }

  const nextDrafts = [...suiteCaseDrafts.value]
  const [currentItem] = nextDrafts.splice(index, 1)
  nextDrafts.splice(nextIndex, 0, currentItem)
  normalizeSuiteCases(nextDrafts)
}

async function handleSaveSuiteCases() {
  // Persists the full suite-case ordering as a replace-all payload.
  if (!currentSuite.value) {
    return
  }

  const payload: SuiteCaseWritePayload[] = suiteCaseDrafts.value.map((item, index) => ({
    testCaseId: item.testCaseId,
    sortOrder: index + 1
  }))

  savingCases.value = true

  try {
    await replaceSuiteCases(currentSuite.value.id, payload)
    caseDialogVisible.value = false
    ElMessage.success('套件编排已保存。')
    await loadPageData()
    await loadSuiteDetail(currentSuite.value.id)
  } finally {
    savingCases.value = false
  }
}

async function loadSuiteDetail(suiteId: number | null) {
  // @param suiteId Selected suite id, or null when the detail panel should be cleared.
  if (!suiteId) {
    currentSuite.value = null
    readinessSummary.value = null
    runForm.testSuiteId = 0
    return
  }

  loading.value = true

  try {
    currentSuite.value = await getTestSuiteDetail(suiteId)
    runForm.testSuiteId = suiteId
    await inspectSuiteReadiness()
  } finally {
    loading.value = false
  }
}

async function handleRun() {
  // Creates a test run from the selected suite/environment/device after readiness passes.
  if (!runForm.testSuiteId || !runForm.environmentProfileId) {
    ElMessage.warning('请先补齐套件与环境信息。')
    return
  }

  if (!canRunSuite.value) {
    ElMessage.warning(primaryReadinessMessage.value || '当前套件尚未满足执行条件。')
    return
  }

  submitting.value = true
  gateState.value = 'submitting'

  try {
    const run = await createTestRun(runForm)
    ElMessage.success(`执行批次 ${run.id} 已创建。`)
    await router.push(`/runs/${run.id}`)
  } catch (error) {
    const issues =
      error instanceof ApiError ? readinessIssuesFromErrorDetails(error.details) : []
    if (issues.length > 0) {
      readinessSummary.value = {
        scope: 'execution_selection',
        status: 'blocked',
        workspaceId: 0,
        testSuiteId: runForm.testSuiteId,
        environmentProfileId: runForm.environmentProfileId,
        deviceProfileId: runForm.deviceProfileId,
        activeEnvironmentCount: 0,
        activeTestSuiteCount: 0,
        blockingIssueCount: issues.length,
        issues
      }
      gateState.value = 'blocked'
    } else {
      gateState.value = 'check_failed'
    }
    ElMessage.error(formatRunCreationError(error))
  } finally {
    submitting.value = false
  }
}

watch(
  () => [runForm.testSuiteId, runForm.environmentProfileId, runForm.deviceProfileId] as const,
  () => {
    readinessSummary.value = null
    gateState.value = runForm.testSuiteId && runForm.environmentProfileId ? 'checking' : 'idle'
    void inspectSuiteReadiness()
  }
)

watch(
  selectedSuiteId,
  async (suiteId) => {
    await loadSuiteDetail(suiteId)
  },
  { immediate: true }
)

onMounted(async () => {
  await loadPageData()
  await loadSuiteDetail(selectedSuiteId.value)
})
</script>

<template>
  <div class="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
    <SectionCard
      description="创建、维护并编排可重复执行的回归套件。"
      title="套件列表"
    >
      <template #action>
        <el-button
          color="#2563eb"
          @click="openCreateSuiteDialog"
        >
          新建套件
        </el-button>
      </template>

      <el-empty
        v-if="suites.length === 0 && !loading"
        description="当前工作空间暂无套件"
      />

      <div
        v-else
        class="space-y-3"
      >
        <button
          v-for="suite in suites"
          :key="suite.id"
          :class="[
            'w-full rounded-2xl border p-4 text-left transition',
            selectedSuiteId === suite.id
              ? 'border-brand-500 bg-brand-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          ]"
          type="button"
          @click="selectedSuiteId = suite.id"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                {{ suite.name }}
              </p>
              <p class="mb-0 mt-2 text-sm text-slate-500">
                {{ suite.code }}
              </p>
            </div>
            <StatusTag :status="suite.status" />
          </div>
          <p class="mb-0 mt-3 text-xs text-slate-400">
            {{ formatDateTime(suite.updatedAt) }}
          </p>
        </button>
      </div>
    </SectionCard>

    <div class="space-y-6">
      <SectionCard
        description="查看套件状态、用例顺序并维护执行内容。"
        title="套件详情"
      >
        <template #action>
          <div
            v-if="currentSuite"
            class="flex gap-2"
          >
            <el-button plain @click="openEditSuiteDialog">
              编辑信息
            </el-button>
            <el-button plain @click="openCaseDialog">
              编排用例
            </el-button>
            <el-button
              :disabled="currentSuite.status === 'active'"
              color="#2563eb"
              @click="activateCurrentSuite"
            >
              激活套件
            </el-button>
          </div>
        </template>

        <div
          v-if="currentSuite"
          class="space-y-6"
        >
          <div class="grid grid-cols-2 gap-4 2xl:grid-cols-4">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">套件编码</p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ currentSuite.code }}</p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">用例数</p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ currentSuite.cases.length }}</p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">状态</p>
              <div class="mt-3">
                <StatusTag :status="currentSuite.status" />
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">最近更新时间</p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ formatDateTime(currentSuite.updatedAt) }}
              </p>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">套件说明</p>
            <p class="mb-0 mt-3 text-sm leading-6 text-slate-700">
              {{ currentSuite.description || '暂无说明' }}
            </p>
          </div>

          <el-table
            v-loading="loading"
            :data="currentSuite.cases"
            empty-text="当前套件暂无编排用例"
            stripe
          >
            <el-table-column label="顺序" prop="orderNo" width="90" />
            <el-table-column label="用例名称" min-width="260" prop="name" />
            <el-table-column label="测试用例 ID" prop="testCaseId" width="140" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-empty
          v-else
          description="暂无套件详情"
        />
      </SectionCard>

      <SectionCard
        description="选择本次使用的环境与设备，检查通过后再创建执行。"
        title="触发执行"
      >
        <div
          v-if="!hasSuiteSelected"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
        >
          当前工作空间暂无可执行套件，请先完成套件编排后再触发执行。
        </div>

        <div
          v-else-if="gateState === 'idle'"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
        >
          请选择套件和环境，系统会检查当前组合是否可执行。
        </div>

        <div
          v-else-if="gateState === 'checking'"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
        >
          正在检查当前套件、环境与设备组合...
        </div>

        <div
          v-else-if="gateState === 'check_failed'"
          class="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span>暂时无法完成执行检查，请重试。</span>
            <el-button plain size="small" @click="inspectSuiteReadiness">重新检查</el-button>
          </div>
        </div>

        <div
          v-else-if="gateState === 'blocked'"
          class="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4"
        >
          <p class="m-0 text-sm font-medium text-amber-900">
            当前组合暂不可执行
          </p>
          <ul class="mb-0 mt-3 list-disc space-y-2 pl-5 text-sm text-amber-800">
            <li
              v-for="issue in readinessIssues"
              :key="`${issue.code}-${issue.resourceId ?? issue.message}`"
            >
              <button
                v-if="issue.routePath"
                class="cursor-pointer border-none bg-transparent p-0 text-left text-amber-800 underline-offset-2 hover:underline"
                type="button"
                @click="navigateReadinessIssue(issue)"
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
                    @click.stop="navigateReadinessIssue(issue)"
                  >
                    {{ getReadinessActionLabel(issue) }}
                  </el-button>
                </span>
              </button>
              <span v-else>
                <span class="block">{{ issue.message }}</span>
                <span class="mt-1 block text-xs text-amber-700">
                  建议操作：{{ getReadinessSuggestion(issue) }}
                </span>
                <span class="mt-2 block">
                  <el-button
                    v-if="canResolveReadinessByNavigation(issue)"
                    plain
                    size="small"
                  >
                    {{ getReadinessActionLabel(issue) }}
                  </el-button>
                </span>
              </span>
            </li>
          </ul>
        </div>

        <div
          v-else-if="gateState === 'ready'"
          class="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          当前组合可执行，可以创建执行批次。
        </div>

        <div
          v-else
          class="mb-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800"
        >
          正在创建执行批次，请勿重复提交。
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">环境档案</label>
            <el-select
              v-model="runForm.environmentProfileId"
              class="!w-full"
            >
              <el-option
                v-for="item in environmentProfiles"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </div>
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">设备预设</label>
            <el-select
              v-model="runForm.deviceProfileId"
              class="!w-full"
              clearable
              placeholder="可选"
            >
              <el-option
                v-for="item in deviceProfiles"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </div>
          <div class="flex items-end">
            <el-button
              :disabled="!canRunSuite"
              :loading="submitting"
              class="!w-full"
              color="#2563eb"
              size="large"
              @click="handleRun"
            >
              触发执行批次
            </el-button>
          </div>
        </div>
      </SectionCard>
    </div>

    <SuiteFormDialog
      :form="suiteForm"
      :mode="suiteDialogMode"
      :saving-suite="savingSuite"
      :status-options="suiteStatusOptions"
      :visible="suiteDialogVisible"
      @submit="handleSaveSuite"
      @update:visible="suiteDialogVisible = $event"
    />

    <SuiteCaseDialog
      :available-cases-to-add="availableCasesToAdd"
      :saving-cases="savingCases"
      :selected-case-to-add="selectedCaseToAdd"
      :suite-case-drafts="suiteCaseDrafts"
      :visible="caseDialogVisible"
      @add-case="addSuiteCase"
      @move-case="moveSuiteCase"
      @remove-case="removeSuiteCase"
      @save="handleSaveSuiteCases"
      @update:selected-case-to-add="selectedCaseToAdd = $event"
      @update:visible="caseDialogVisible = $event"
    />
  </div>
</template>
