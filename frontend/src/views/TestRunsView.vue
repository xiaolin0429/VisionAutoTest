<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { cancelTestRun, createTestRun, getRunDetail, listTestRuns } from '@/api/modules/testRuns'
import { ApiError } from '@/api/client'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { listTestSuites } from '@/api/modules/testSuites'
import { formatDateTime } from '@/utils/format'
import {
  getRunFailureSuggestion,
  isAttentionRunStatus,
  resolveRunRepairTarget
} from '@/utils/runFailures'
import type { DeviceProfile, EnvironmentProfile, TestRun, TestSuite } from '@/types/models'

const router = useRouter()
const loading = ref(false)
const testRuns = ref<TestRun[]>([])
const repairingRunId = ref<number | null>(null)
let pollTimer: number | null = null

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling'])

const statusFilter = ref('')
const statusFilterOptions = [
  { label: '全部', value: '' },
  { label: '排队中', value: 'queued' },
  { label: '执行中', value: 'running' },
  { label: '已通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '部分失败', value: 'partial_failed' },
  { label: '已取消', value: 'cancelled' }
]

function handleStatusFilterChange() {
  void loadTestRuns()
}

// ── Trigger dialog ────────────────────────────────────────────────────────────
const triggerDialogVisible = ref(false)
const triggerLoading = ref(false)
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
}

async function handleTriggerRun() {
  if (!triggerForm.testSuiteId) {
    ElMessage.warning('请选择测试套件')
    return
  }
  if (!triggerForm.environmentProfileId) {
    ElMessage.warning('请选择执行环境')
    return
  }

  triggerLoading.value = true
  try {
    await createTestRun({
      testSuiteId: triggerForm.testSuiteId,
      environmentProfileId: triggerForm.environmentProfileId,
      deviceProfileId: triggerForm.deviceProfileId
    })
    ElMessage.success('执行批次已创建，正在排队执行…')
    triggerDialogVisible.value = false
    await loadTestRuns()
  } catch {
    ElMessage.error('触发执行失败，请检查套件与环境配置')
  } finally {
    triggerLoading.value = false
  }
}

// ── Runs list ─────────────────────────────────────────────────────────────────
function formatDuration(startedAt: string | null, finishedAt: string | null): string {
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
  if (run.totalCaseCount === 0) return '--'
  return `${Math.round((run.passedCaseCount / run.totalCaseCount) * 100)}%`
}

const metrics = computed(() => {
  const total = testRuns.value.length
  const running = testRuns.value.filter((item) => item.status === 'running').length
  const passed = testRuns.value.filter((item) => item.status === 'passed').length
  const warning = testRuns.value.filter((item) => item.status === 'failed' || item.status === 'partial_failed').length
  const finishedRuns = testRuns.value.filter((item) => item.totalCaseCount > 0)
  const overallPassRate = finishedRuns.length > 0
    ? Math.round(
        (finishedRuns.reduce((sum, item) => sum + item.passedCaseCount, 0) /
          finishedRuns.reduce((sum, item) => sum + item.totalCaseCount, 0)) *
          100
      )
    : 0

  return [
    {
      label: '总执行批次',
      value: total,
      hint: '映射 `test-runs` 集合资源。'
    },
    {
      label: '执行中',
      value: running,
      hint: '运行中批次会自动轮询刷新状态。'
    },
    {
      label: '已通过',
      value: passed,
      hint: '仅统计终态为 passed 的批次。'
    },
    {
      label: '需关注',
      value: warning,
      hint: '包含 failed 与 partial_failed 状态。'
    },
    {
      label: '用例通过率',
      value: `${overallPassRate}%`,
      hint: '所有批次的用例通过率汇总。'
    }
  ]
})

function clearPollTimer() {
  if (pollTimer === null) {
    return
  }

  window.clearTimeout(pollTimer)
  pollTimer = null
}

function scheduleTestRunsRefresh() {
  clearPollTimer()
  pollTimer = window.setTimeout(() => {
    void loadTestRuns({ silent: true })
  }, 3000)
}

async function loadTestRuns(options: { silent?: boolean } = {}) {
  if (!options.silent || testRuns.value.length === 0) {
    loading.value = true
  }

  try {
    testRuns.value = await listTestRuns(
      statusFilter.value ? { status: statusFilter.value } : undefined
    )

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
  void router.push(`/runs/${testRunId}`)
}

async function openRunRepair(testRunId: number) {
  repairingRunId.value = testRunId
  try {
    const detail = await getRunDetail(testRunId)
    const repairTarget = resolveRunRepairTarget(detail)
    if (!repairTarget) {
      ElMessage.warning('当前批次没有可定位的失败资源，请查看执行详情。')
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
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-5 gap-4">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <SectionCard
      description="遵循异步资源模式：先创建 `test-runs`，再轮询批次、case-runs 与 step-results。"
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
        :data="testRuns"
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
          min-width="160"
        >
          <template #default="{ row }">
            {{ row.passedCaseCount }}/{{ row.totalCaseCount }} 通过
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
                row.totalCaseCount > 0 && row.passedCaseCount === row.totalCaseCount
                  ? 'text-green-600'
                  : row.totalCaseCount > 0 && row.passedCaseCount === 0
                    ? 'text-red-600'
                    : 'text-slate-600'
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
          width="160"
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
      width="480px"
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
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="triggerDialogVisible = false">
            取消
          </el-button>
          <el-button
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
