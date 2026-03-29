<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listTestRuns } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type { TestRun } from '@/types/models'

const router = useRouter()
const loading = ref(false)
const testRuns = ref<TestRun[]>([])
let pollTimer: number | null = null

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling'])

const metrics = computed(() => {
  const total = testRuns.value.length
  const running = testRuns.value.filter((item) => item.status === 'running').length
  const passed = testRuns.value.filter((item) => item.status === 'passed').length
  const warning = testRuns.value.filter((item) => item.status === 'failed' || item.status === 'partial_failed').length

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
  void router.push(`/runs/${testRunId}`)
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-4 gap-4">
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
          min-width="180"
        >
          <template #default="{ row }">
            {{ row.passedCaseCount }}/{{ row.totalCaseCount }} 通过
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
          label="操作"
          width="120"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              @click="openRunDetail(row.id)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>
