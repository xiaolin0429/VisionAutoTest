<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { cancelTestRun, createTestRun, getRunDetail, getTestRunReport, listTestRuns, rerunFailedCases } from '@/api/modules/testRuns'
import { ApiError } from '@/api/client'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { getTestSuiteExecutionReadiness, listTestSuites } from '@/api/modules/testSuites'
import { formatDateTime, formatPercent } from '@/utils/format'
import {
  getRunFailureSuggestion,
  isAttentionRunStatus,
  resolveRunRepairTarget
} from '@/utils/runFailures'
import {
  buildCaseResultDistribution,
  calculateAggregateCasePassRate,
  calculateCasePassRate,
  calculateRunMetrics
} from '@/utils/runMetrics'
import {
  buildReadinessNavigation,
  getReadinessActionLabel,
  getReadinessSuggestion,
  readinessIssuesFromErrorDetails,
  type ExecutionGateState
} from '@/utils/readiness'
import type { DeviceProfile, EnvironmentProfile, ExecutionReadinessSummary, TestRun, TestSuite } from '@/types/models'

const router = useRouter()
const loading = ref(false)
const testRuns = ref<TestRun[]>([])
const repairingRunId = ref<number | null>(null)
const rerunFailedRunId = ref<number | null>(null)
let pollTimer: number | null = null

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling'])

const statusFilter = ref('')
const statusFilterOptions = [
  { label: '全部', value: '' },
  { label: '排队中', value: 'queued' },
  { label: '执行中', value: 'running' },
  { label: '取消中', value: 'cancelling' },
  { label: '已通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '部分失败', value: 'partial_failed' },
  { label: '异常', value: 'error' },
  { label: '需关注', value: 'attention' },
  { label: '已取消', value: 'cancelled' }
]

function handleStatusFilterChange() {
  clearPollTimer()
  if (testRuns.value.some((item) => ACTIVE_RUN_STATUSES.has(item.status))) {
    scheduleTestRunsRefresh()
  }
}

const filteredTestRuns = computed(() => {
  if (!statusFilter.value) return testRuns.value
  if (statusFilter.value === 'attention') {
    return testRuns.value.filter((item) => isAttentionRunStatus(item.status))
  }
  return testRuns.value.filter((item) => item.status === statusFilter.value)
})

// ── Trigger dialog ────────────────────────────────────────────────────────────
const triggerDialogVisible = ref(false)
const triggerLoading = ref(false)
const triggerGateState = ref<ExecutionGateState>('idle')
const triggerReadiness = ref<ExecutionReadinessSummary | null>(null)
let triggerReadinessRequestId = 0
const suites = ref<TestSuite[]>([])
const environments = ref<EnvironmentProfile[]>([])
const devices = ref<DeviceProfile[]>([])

const triggerForm = reactive<{
  testSuiteId: number | null
  environmentProfileId: number | null
  deviceProfileId: number | null
}>({
  testSuiteId: null,
  environmentProfileId: null,
  deviceProfileId: null
})

async function openTriggerDialog() {
  // Opens the trigger dialog and hydrates active suite/environment/device options for run creation.
  triggerForm.testSuiteId = null
  triggerForm.environmentProfileId = null
  triggerForm.deviceProfileId = null
  triggerDialogVisible.value = true

  const [suiteList, envList, deviceList] = await Promise.all([
    listTestSuites(),
    listEnvironmentProfiles(),
    listDeviceProfiles()
  ])

  suites.value = suiteList.filter((s) => s.status === 'active')
  environments.value = envList.filter((e) => e.status === 'active')
  devices.value = deviceList
  triggerForm.testSuiteId = suites.value[0]?.id ?? null
  triggerForm.environmentProfileId = environments.value[0]?.id ?? null
  triggerForm.deviceProfileId = null
}

const triggerIssues = computed(() => triggerReadiness.value?.issues ?? [])
const canTriggerRun = computed(() =>
  triggerGateState.value === 'ready' && !triggerLoading.value
)

async function inspectTriggerReadiness() {
  if (!triggerForm.testSuiteId || !triggerForm.environmentProfileId) {
    triggerReadinessRequestId += 1
    triggerReadiness.value = null
    triggerGateState.value = 'idle'
    return
  }

  const requestId = ++triggerReadinessRequestId
  triggerReadiness.value = null
  triggerGateState.value = 'checking'
  try {
    const summary = await getTestSuiteExecutionReadiness(triggerForm.testSuiteId, {
      environmentProfileId: triggerForm.environmentProfileId,
      deviceProfileId: triggerForm.deviceProfileId
    })
    if (requestId !== triggerReadinessRequestId) return
    triggerReadiness.value = summary
    triggerGateState.value = summary.status === 'ready' ? 'ready' : 'blocked'
  } catch {
    if (requestId !== triggerReadinessRequestId) return
    triggerGateState.value = 'check_failed'
  }
}

function navigateTriggerIssue(issue: ExecutionReadinessSummary['issues'][number]) {
  const target = buildReadinessNavigation(issue)
  if (!target) return
  triggerDialogVisible.value = false
  void router.push(target)
}

async function handleTriggerRun() {
  // Submits the trigger form as a new test-run request and refreshes the run list on success.
  if (!triggerForm.testSuiteId) {
    ElMessage.warning('请选择测试套件')
    return
  }
  if (!triggerForm.environmentProfileId) {
    ElMessage.warning('请选择执行环境')
    return
  }

  if (!canTriggerRun.value) {
    ElMessage.warning(triggerIssues.value[0]?.message ?? '请等待当前组合检查通过。')
    return
  }

  triggerLoading.value = true
  triggerGateState.value = 'submitting'
  try {
    await createTestRun({
      testSuiteId: triggerForm.testSuiteId,
      environmentProfileId: triggerForm.environmentProfileId,
      deviceProfileId: triggerForm.deviceProfileId
    })
    ElMessage.success('执行批次已创建，正在排队执行…')
    triggerDialogVisible.value = false
    await loadTestRuns()
  } catch (error) {
    const issues = error instanceof ApiError
      ? readinessIssuesFromErrorDetails(error.details)
      : []
    if (issues.length > 0) {
      triggerReadiness.value = {
        scope: 'execution_selection',
        status: 'blocked',
        workspaceId: 0,
        testSuiteId: triggerForm.testSuiteId,
        environmentProfileId: triggerForm.environmentProfileId,
        deviceProfileId: triggerForm.deviceProfileId,
        activeEnvironmentCount: 0,
        activeTestSuiteCount: 0,
        blockingIssueCount: issues.length,
        issues
      }
      triggerGateState.value = 'blocked'
      ElMessage.error(issues[0]?.message ?? '当前组合不可执行')
    } else {
      triggerGateState.value = 'check_failed'
      ElMessage.error(error instanceof Error ? error.message : '触发执行失败，请稍后重试')
    }
  } finally {
    triggerLoading.value = false
  }
}

watch(
  () => [
    triggerForm.testSuiteId,
    triggerForm.environmentProfileId,
    triggerForm.deviceProfileId
  ] as const,
  () => {
    triggerReadiness.value = null
    triggerGateState.value =
      triggerForm.testSuiteId && triggerForm.environmentProfileId ? 'checking' : 'idle'
    void inspectTriggerReadiness()
  }
)

// ── Runs list ─────────────────────────────────────────────────────────────────
function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  // @param startedAt Run start timestamp, or null before execution begins.
  // @param finishedAt Run finish timestamp, or null while the run is still active.
  if (!startedAt) return '--'
  if (!finishedAt) return '进行中'
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime()
  if (ms < 0) return '--'
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  return `${minutes}m ${remainSeconds}s`
}

function formatPassRate(run: TestRun): string {
  // @param run Test-run list item containing aggregate case counters.
  return formatPercent(calculateCasePassRate(run))
}

function passRateClass(run: TestRun): string {
  const passRate = calculateCasePassRate(run)
  if (passRate === 100) return 'text-green-600'
  if (passRate === 0) return 'text-red-600'
  return 'text-slate-600'
}

const metrics = computed(() => {
  const runMetrics = calculateRunMetrics(testRuns.value)
  const running = testRuns.value.filter((item) => item.status === 'running').length
  const overallPassRate = calculateAggregateCasePassRate(testRuns.value)

  return [
    {
      label: '总执行批次',
      value: runMetrics.total,
      hint: '当前工作空间中的全部执行批次。'
    },
    {
      label: '执行中',
      value: running,
      hint: '运行中批次会自动轮询刷新状态。'
    },
    {
      label: '已通过',
      value: runMetrics.passed,
      hint: '仅统计已通过的终态批次。'
    },
    {
      label: '需关注',
      value: runMetrics.attention,
      hint: '包含失败、部分失败与异常。'
    },
    {
      label: '用例通过率',
      value: formatPercent(overallPassRate),
      hint: '按通过、失败、异常用例计算。'
    }
  ]
})

function clearPollTimer() {
  // Stops the runs-list polling loop, if currently scheduled.
  if (pollTimer === null) {
    return
  }

  window.clearTimeout(pollTimer)
  pollTimer = null
}

function scheduleTestRunsRefresh() {
  // Schedules the next silent list refresh while at least one run remains active.
  clearPollTimer()
  pollTimer = window.setTimeout(() => {
    void loadTestRuns({ silent: true })
  }, 3000)
}

async function loadTestRuns(options: { silent?: boolean } = {}) {
  // @param options.silent When true, refresh the list without showing the page-level loading state.
  if (!options.silent || testRuns.value.length === 0) {
    loading.value = true
  }

  try {
    testRuns.value = await listTestRuns()

    if (testRuns.value.some((item) => ACTIVE_RUN_STATUSES.has(item.status))) {
      scheduleTestRunsRefresh()
      return
    }

    clearPollTimer()
  } finally {
    if (!options.silent || testRuns.value.length === 0) {
      loading.value = false
    }
  }
}

onMounted(async () => {
  await loadTestRuns()
})

onBeforeUnmount(() => {
  clearPollTimer()
})

function openRunDetail(testRunId: number) {
  // @param testRunId Run id whose detail page should be opened.
  void router.push(`/runs/${testRunId}`)
}

async function openRunRepair(testRunId: number) {
  // @param testRunId Run id used to resolve the most relevant repair target from run detail.
  repairingRunId.value = testRunId
  try {
    const [detail, report] = await Promise.all([
      getRunDetail(testRunId),
      getTestRunReport(testRunId)
    ])
    const repairTarget = resolveRunRepairTarget(detail, report?.summary.failure)
    if (!repairTarget) {
      ElMessage.warning('当前批次没有可定位的失败资源，请查看执行详情。')
      void router.push(`/runs/${testRunId}`)
      return
    }

    if (!repairTarget.path) {
      ElMessage.info('该问题归因于平台运行环境，请进入详情重试或查看技术信息。')
      void router.push(`/runs/${testRunId}`)
      return
    }
    void router.push({ path: repairTarget.path, query: repairTarget.query })
  } catch {
    ElMessage.error('定位失败资源失败，请先进入执行详情查看。')
    void router.push(`/runs/${testRunId}`)
  } finally {
    repairingRunId.value = null
  }
}

async function handleCancelRun(testRunId: number) {
  // @param testRunId Active run id to transition into cancelling state.
  try {
    await ElMessageBox.confirm(
      '取消后正在执行的用例将中止，已完成的用例结果将保留。',
      '确认取消执行',
      { confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    await cancelTestRun(testRunId)
    ElMessage.success('执行批次已标记为取消中')
    await loadTestRuns()
  } catch (error) {
    if (error instanceof ApiError && error.code === 'TEST_RUN_STATUS_CONFLICT') {
      ElMessage.warning('该批次状态已变更，无法取消')
    } else {
      ElMessage.error('取消执行失败，请稍后重试')
    }
  }
}

async function handleRerunFailed(testRunId: number) {
  // @param testRunId Source run whose failed/errored cases should be rerun.
  rerunFailedRunId.value = testRunId
  try {
    const newRun = await rerunFailedCases(testRunId)
    ElMessage.success('重跑批次已创建，正在跳转…')
    void router.push(`/runs/${newRun.id}`)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'NO_FAILED_CASES_TO_RERUN') {
      ElMessage.warning('该批次无失败用例，无需重跑')
    } else {
      ElMessage.error('重跑失败，请稍后重试')
    }
  } finally {
    rerunFailedRunId.value = null
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-2 gap-4 xl:grid-cols-5">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <SectionCard
      description="筛选执行结果，查看需关注批次并快速定位问题。"
      title="执行批次"
    >
      <template #action>
        <el-button
          color="#2563eb"
          @click="openTriggerDialog"
        >
          触发执行
        </el-button>
      </template>

      <div class="mb-4 flex flex-wrap gap-2">
        <el-button
          v-for="option in statusFilterOptions"
          :key="option.value || 'all'"
          :plain="statusFilter !== option.value"
          :type="statusFilter === option.value ? 'primary' : undefined"
          size="small"
          @click="statusFilter = option.value; handleStatusFilterChange()"
        >
          {{ option.label }}
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="filteredTestRuns"
        :empty-text="statusFilter ? '当前筛选条件下暂无执行批次，可切换到全部状态' : '当前工作空间暂无执行批次'"
        stripe
      >
        <el-table-column
          label="批次 ID"
          prop="id"
          width="120"
        />
        <el-table-column
          label="套件"
          min-width="220"
          prop="suiteName"
        />
        <el-table-column
          label="环境"
          min-width="160"
          prop="environmentName"
        />
        <el-table-column
          label="设备"
          min-width="180"
          prop="deviceName"
        />
        <el-table-column
          label="状态"
          width="120"
        >
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column
          label="用例统计"
          min-width="220"
        >
          <template #default="{ row }">
            <div class="flex items-center gap-1 whitespace-nowrap text-xs text-slate-600">
              <template
                v-for="(item, index) in buildCaseResultDistribution(row)"
                :key="item.key"
              >
                <span
                  :class="{
                    'text-emerald-700': item.key === 'passed',
                    'text-red-700': item.key === 'failed',
                    'text-amber-700': item.key === 'error'
                  }"
                >
                  {{ item.label }} {{ item.count }}
                </span>
                <span
                  v-if="index < 2"
                  aria-hidden="true"
                  class="text-slate-300"
                >·</span>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="通过率"
          width="100"
        >
          <template #default="{ row }">
            <span
              :class="[
                'font-medium',
                passRateClass(row)
              ]"
            >
              {{ formatPassRate(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="耗时"
          width="110"
        >
          <template #default="{ row }">
            {{ formatDuration(row.startedAt, row.finishedAt) }}
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
        <el-table-column
          label="修复建议"
          min-width="260"
        >
          <template #default="{ row }">
            <div v-if="isAttentionRunStatus(row.status)" class="space-y-2">
              <p class="m-0 text-xs leading-5 text-amber-700">
                {{ getRunFailureSuggestion(row) }}
              </p>
              <el-button
                plain
                size="small"
                :loading="repairingRunId === row.id"
                @click="openRunRepair(row.id)"
              >
                去定位失败资源
              </el-button>
            </div>
            <span v-else class="text-xs text-slate-400">--</span>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          fixed="right"
          width="170"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              @click="openRunDetail(row.id)"
            >
              查看详情
            </el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'partial_failed' || row.status === 'error'"
              link
              type="warning"
              :loading="rerunFailedRunId === row.id"
              @click="handleRerunFailed(row.id)"
            >
              重跑失败项
            </el-button>
            <el-button
              v-if="row.status === 'queued' || row.status === 'running'"
              link
              type="danger"
              @click="handleCancelRun(row.id)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>

    <el-dialog
      v-model="triggerDialogVisible"
      title="触发执行"
      width="min(92vw, 560px)"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">
            测试套件
            <span class="text-red-500">*</span>
          </label>
          <el-select
            v-model="triggerForm.testSuiteId"
            class="!w-full"
            placeholder="请选择套件"
          >
            <el-option
              v-for="suite in suites"
              :key="suite.id"
              :label="suite.name"
              :value="suite.id"
            />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">
            执行环境
            <span class="text-red-500">*</span>
          </label>
          <el-select
            v-model="triggerForm.environmentProfileId"
            class="!w-full"
            placeholder="请选择环境"
          >
            <el-option
              v-for="env in environments"
              :key="env.id"
              :label="env.name"
              :value="env.id"
            />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">设备档案（可选）</label>
          <el-select
            v-model="triggerForm.deviceProfileId"
            class="!w-full"
            clearable
            placeholder="不指定设备"
          >
            <el-option
              v-for="device in devices"
              :key="device.id"
              :label="device.name"
              :value="device.id"
            />
          </el-select>
        </div>

        <div
          v-if="triggerGateState === 'idle'"
          class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
        >
          请选择套件和环境，系统会检查当前组合是否可执行。
        </div>
        <div
          v-else-if="triggerGateState === 'checking'"
          class="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800"
        >
          正在检查当前套件、环境与设备组合...
        </div>
        <div
          v-else-if="triggerGateState === 'check_failed'"
          class="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <div class="flex items-center justify-between gap-3">
            <span>暂时无法完成执行检查，请重试。</span>
            <el-button plain size="small" @click="inspectTriggerReadiness">重新检查</el-button>
          </div>
        </div>
        <div
          v-else-if="triggerGateState === 'blocked'"
          class="rounded-2xl border border-amber-200 bg-amber-50 p-4"
        >
          <p class="m-0 text-sm font-medium text-amber-900">当前组合暂不可执行</p>
          <div class="mt-3 space-y-3">
            <div
              v-for="issue in triggerIssues"
              :key="`${issue.code}-${issue.resourceId ?? issue.message}`"
              class="rounded-xl border border-amber-100 bg-white p-3"
            >
              <p class="m-0 text-sm text-amber-900">{{ issue.message }}</p>
              <p class="mb-0 mt-1 text-xs text-amber-700">
                建议操作：{{ getReadinessSuggestion(issue) }}
              </p>
              <el-button
                v-if="issue.routePath"
                class="!mt-2"
                plain
                size="small"
                @click="navigateTriggerIssue(issue)"
              >
                {{ getReadinessActionLabel(issue) }}
              </el-button>
            </div>
          </div>
        </div>
        <div
          v-else-if="triggerGateState === 'ready'"
          class="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          当前组合可执行，可以创建执行批次。
        </div>
        <div
          v-else
          class="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800"
        >
          正在创建执行批次，请勿重复提交。
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="triggerDialogVisible = false">
            取消
          </el-button>
          <el-button
            :disabled="!canTriggerRun"
            :loading="triggerLoading"
            color="#2563eb"
            @click="handleTriggerRun"
          >
            确认执行
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
