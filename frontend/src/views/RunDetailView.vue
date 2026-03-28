<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getRunDetail } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type { CaseRun, RunDetail } from '@/types/models'

const route = useRoute()
const loading = ref(false)
const runDetail = ref<RunDetail | null>(null)
const selectedCaseRunId = ref<number | null>(null)

const currentCaseRun = computed(() => {
  return runDetail.value?.caseRuns.find((item) => item.id === selectedCaseRunId.value) ?? null
})

const metrics = computed(() => {
  if (!runDetail.value) {
    return []
  }

  return [
    {
      label: '总用例数',
      value: runDetail.value.summary.totalCases,
      hint: '取自 test-run 聚合统计字段。'
    },
    {
      label: '通过用例',
      value: runDetail.value.summary.passedCases,
      hint: '来自 case-runs 聚合统计。'
    },
    {
      label: '失败用例',
      value: runDetail.value.summary.failedCases,
      hint: '失败后可继续下钻 step-results。'
    },
    {
      label: '执行耗时',
      value: `${runDetail.value.summary.durationSeconds}s`,
      hint: '由 started_at / finished_at 聚合计算。'
    }
  ]
})

async function loadRunDetail() {
  loading.value = true
  try {
    const testRunId = Number(route.params.testRunId)
    const payload = await getRunDetail(testRunId)
    runDetail.value = payload
    selectedCaseRunId.value = payload.caseRuns[0]?.id ?? null
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.testRunId,
  () => {
    void loadRunDetail()
  }
)

onMounted(async () => {
  await loadRunDetail()
})

function selectCaseRun(caseRun: CaseRun) {
  selectedCaseRunId.value = caseRun.id
}
</script>

<template>
  <div class="space-y-6">
    <SectionCard
      description="当前页面以 `test-runs`、`case-runs`、`step-results` 三层真实接口做聚合。"
      title="执行总览"
    >
      <template #action>
        <StatusTag
          v-if="runDetail"
          :status="runDetail.status"
        />
      </template>

      <div
        v-if="runDetail"
        class="space-y-6"
      >
        <div class="grid grid-cols-4 gap-4">
          <MetricCard
            v-for="metric in metrics"
            :key="metric.label"
            :hint="metric.hint"
            :label="metric.label"
            :value="metric.value"
          />
        </div>

        <div class="grid grid-cols-4 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              套件
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ runDetail.suiteName }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              环境
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ runDetail.environmentName }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              设备
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ runDetail.deviceName }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              创建时间
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ formatDateTime(runDetail.createdAt) }}
            </p>
          </div>
        </div>
      </div>
    </SectionCard>

    <div class="grid grid-cols-[440px_minmax(0,1fr)] gap-6">
      <SectionCard
        description="点击某个 case-run 可查看对应步骤执行结果。"
        title="用例执行实例"
      >
        <el-table
          v-loading="loading"
          :data="runDetail?.caseRuns ?? []"
          highlight-current-row
          stripe
          @row-click="selectCaseRun"
        >
          <el-table-column
            label="用例名称"
            min-width="220"
            prop="name"
          />
          <el-table-column
            label="状态"
            width="110"
          >
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column
            label="Diff"
            prop="diffCount"
            width="90"
          />
        </el-table>
      </SectionCard>

      <SectionCard
        description="step-results 展示真实执行步骤；若用例含 `component_call`，这里会展示展开后的线性执行序列。"
        title="真实步骤结果"
      >
        <div
          v-if="currentCaseRun"
          class="space-y-6"
        >
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between">
              <h4 class="m-0 text-base font-semibold text-slate-900">
                {{ currentCaseRun.name }}
              </h4>
              <StatusTag :status="currentCaseRun.status" />
            </div>
            <p class="mb-2 mt-0 text-sm text-slate-500">
              执行耗时：{{ currentCaseRun.durationMs }} ms
            </p>
            <p class="m-0 text-sm text-slate-500">
              失败摘要：{{ currentCaseRun.failureSummary }}
            </p>
          </div>

          <el-timeline>
            <el-timeline-item
              v-for="step in currentCaseRun.steps"
              :key="step.id"
              :timestamp="`Step ${step.stepNo}`"
              placement="top"
            >
              <div class="rounded-2xl border border-slate-200 bg-white p-4">
                <div class="mb-3 flex items-center justify-between">
                  <p class="m-0 font-medium text-slate-900">
                    {{ step.name }}
                  </p>
                  <StatusTag :status="step.status" />
                </div>
                <p class="m-0 text-sm leading-6 text-slate-500">
                  {{ step.message }}
                </p>
                <p class="mb-0 mt-2 text-xs text-slate-400">
                  类型：{{ step.type }} · 耗时：{{ step.durationMs ?? 0 }} ms
                </p>
                <p
                  v-if="step.artifactLabel"
                  class="mb-0 mt-2 text-xs uppercase tracking-wide text-slate-400"
                >
                  artifact: {{ step.artifactLabel }}
                </p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>

        <el-empty
          v-else
          description="当前执行暂无步骤结果"
        />
      </SectionCard>
    </div>
  </div>
</template>
