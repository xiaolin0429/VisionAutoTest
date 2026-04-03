<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getMediaObject, getMediaObjectContent } from '@/api/modules/mediaObjects'
import {
  createTestRun,
  getRunDetail,
  getTestRunReport,
  listReportArtifacts
} from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import {
  resolveRunRepairTarget
} from '@/utils/runFailures'
import type {
  CaseRun,
  MediaObject,
  ReportArtifact,
  RunDetail,
  RunReport,
  StepResult
} from '@/types/models'

interface StepMediaEntry {
  label: string
  mediaObjectId: number
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const reportLoading = ref(false)
const rerunLoading = ref(false)
const runDetail = ref<RunDetail | null>(null)
const runReport = ref<RunReport | null>(null)
const reportArtifacts = ref<ReportArtifact[]>([])
const selectedCaseRunId = ref<number | null>(null)

const mediaObjectMap = ref<Record<number, MediaObject>>({})
const mediaPreviewMap = ref<Record<number, string>>({})
const mediaLoadingMap = ref<Record<number, boolean>>({})
const mediaErrorMap = ref<Record<number, string>>({})

let pollTimer: number | null = null

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling'])

const currentCaseRun = computed(() => {
  return runDetail.value?.caseRuns.find((item) => item.id === selectedCaseRunId.value) ?? null
})

const repairSummary = computed(() => {
  const repairTarget = resolveRunRepairTarget(runDetail.value)
  if (!repairTarget) {
    return null
  }

  return {
    title: `优先修复：${repairTarget.caseRunName}`,
    summary: repairTarget.failureSummary,
    actionLabel: repairTarget.label,
    path: repairTarget.path,
    query: repairTarget.query
  }
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

const reportSummaryCards = computed(() => {
  if (!runReport.value) {
    return []
  }

  const summary = runReport.value.summary

  return [
    { label: '总用例数', value: String(summary.counts.total) },
    { label: '通过', value: String(summary.counts.passed) },
    { label: '失败', value: String(summary.counts.failed) },
    { label: '异常/取消', value: `${summary.counts.error} / ${summary.counts.cancelled}` }
  ]
})

const reportArtifactTypeEntries = computed(() => {
  if (!runReport.value) {
    return []
  }

  return Object.entries(runReport.value.summary.artifacts.byType)
})

function clearPollTimer() {
  if (pollTimer === null) {
    return
  }

  window.clearTimeout(pollTimer)
  pollTimer = null
}

function shouldPollRunDetail(detail: RunDetail) {
  return ACTIVE_RUN_STATUSES.has(detail.status)
}

function scheduleRunDetailRefresh() {
  clearPollTimer()
  pollTimer = window.setTimeout(() => {
    void loadRunDetail({ silent: true })
  }, 3000)
}

function revokePreviewUrls() {
  Object.values(mediaPreviewMap.value).forEach((url) => URL.revokeObjectURL(url))
  mediaPreviewMap.value = {}
}

function getStepMediaEntries(step: StepResult): StepMediaEntry[] {
  const entries: StepMediaEntry[] = []

  if (step.expectedMediaObjectId !== null) {
    entries.push({
      label: '基准图',
      mediaObjectId: step.expectedMediaObjectId
    })
  }

  if (step.actualMediaObjectId !== null) {
    entries.push({
      label: '实际截图',
      mediaObjectId: step.actualMediaObjectId
    })
  }

  if (step.diffMediaObjectId !== null) {
    entries.push({
      label: 'Diff 图',
      mediaObjectId: step.diffMediaObjectId
    })
  }

  return entries
}

async function ensureMediaLoaded(mediaObjectId: number) {
  if (mediaPreviewMap.value[mediaObjectId] || mediaLoadingMap.value[mediaObjectId]) {
    return
  }

  mediaLoadingMap.value = {
    ...mediaLoadingMap.value,
    [mediaObjectId]: true
  }

  try {
    const [metadata, blob] = await Promise.all([
      mediaObjectMap.value[mediaObjectId]
        ? Promise.resolve(mediaObjectMap.value[mediaObjectId])
        : getMediaObject(mediaObjectId),
      getMediaObjectContent(mediaObjectId)
    ])

    mediaObjectMap.value = {
      ...mediaObjectMap.value,
      [mediaObjectId]: metadata
    }
    mediaPreviewMap.value = {
      ...mediaPreviewMap.value,
      [mediaObjectId]: URL.createObjectURL(blob)
    }
  } catch (error) {
    mediaErrorMap.value = {
      ...mediaErrorMap.value,
      [mediaObjectId]: error instanceof Error ? error.message : '媒体加载失败'
    }
  } finally {
    mediaLoadingMap.value = {
      ...mediaLoadingMap.value,
      [mediaObjectId]: false
    }
  }
}

async function warmupCurrentCaseMedia(caseRun: CaseRun | null) {
  if (!caseRun) {
    return
  }

  const mediaIds = caseRun.steps.flatMap((step) =>
    getStepMediaEntries(step).map((item) => item.mediaObjectId)
  )

  await Promise.all(mediaIds.map((mediaObjectId) => ensureMediaLoaded(mediaObjectId)))
}

async function warmupReportArtifactMedia(artifacts: ReportArtifact[]) {
  const mediaIds = artifacts
    .map((item) => item.mediaObjectId)
    .filter((item): item is number => item !== null)

  await Promise.all(mediaIds.map((mediaObjectId) => ensureMediaLoaded(mediaObjectId)))
}

async function loadRunReport(testRunId: number) {
  reportLoading.value = true

  try {
    const report = await getTestRunReport(testRunId)
    runReport.value = report

    if (!report) {
      reportArtifacts.value = []
      return
    }

    const artifacts = await listReportArtifacts(report.id)
    reportArtifacts.value = artifacts
    await warmupReportArtifactMedia(artifacts)
  } finally {
    reportLoading.value = false
  }
}

async function syncRunReport(testRunId: number, detail: RunDetail) {
  if (shouldPollRunDetail(detail) && runReport.value === null) {
    reportArtifacts.value = []
    return
  }

  await loadRunReport(testRunId)
}

async function loadRunDetail(options: { silent?: boolean } = {}) {
  if (!options.silent || runDetail.value === null) {
    loading.value = true
  }

  try {
    const testRunId = Number(route.params.testRunId)
    const payload = await getRunDetail(testRunId)

    // 优化：优先选择第一个失败或异常的用例
    const failedCaseRun = payload.caseRuns.find((item) =>
      item.status === 'failed' || item.status === 'error'
    )

    const nextSelectedCaseRunId =
      selectedCaseRunId.value !== null &&
      payload.caseRuns.some((item) => item.id === selectedCaseRunId.value)
        ? selectedCaseRunId.value
        : failedCaseRun?.id ?? payload.caseRuns[0]?.id ?? null

    runDetail.value = payload
    selectedCaseRunId.value = nextSelectedCaseRunId

    await Promise.all([
      warmupCurrentCaseMedia(
        payload.caseRuns.find((item) => item.id === nextSelectedCaseRunId) ?? null
      ),
      syncRunReport(testRunId, payload)
    ])

    if (shouldPollRunDetail(payload)) {
      scheduleRunDetailRefresh()
      return
    }

    clearPollTimer()
  } finally {
    if (!options.silent || runDetail.value === null) {
      loading.value = false
    }
  }
}

async function downloadMedia(mediaObjectId: number) {
  try {
    await ensureMediaLoaded(mediaObjectId)
    const url = mediaPreviewMap.value[mediaObjectId]
    const media = mediaObjectMap.value[mediaObjectId]
    if (!url || !media) {
      ElMessage.error('当前媒体尚未加载完成。')
      return
    }

    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = media.fileName
    anchor.click()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '下载失败，请稍后重试。')
  }
}

function selectCaseRun(caseRun: CaseRun) {
  selectedCaseRunId.value = caseRun.id
}

function buildRunSummaryText(detail: RunDetail): string {
  const passRate = detail.summary.totalCases > 0
    ? Math.round((detail.summary.passedCases / detail.summary.totalCases) * 100)
    : 0

  const lines: string[] = [
    `[执行摘要] 批次 #${detail.id}`,
    `套件: ${detail.suiteName}`,
    `环境: ${detail.environmentName} | 设备: ${detail.deviceName}`,
    `状态: ${detail.status} | 通过率: ${passRate}% (${detail.summary.passedCases}/${detail.summary.totalCases})`,
    `耗时: ${detail.summary.durationSeconds}s | 创建: ${formatDateTime(detail.createdAt)}`
  ]

  const failedCases = detail.caseRuns.filter(
    (c) => c.status === 'failed' || c.status === 'error'
  )

  if (failedCases.length > 0) {
    lines.push('', `--- 失败用例 (${failedCases.length}) ---`)

    for (const caseRun of failedCases) {
      lines.push(``, `[${caseRun.status.toUpperCase()}] ${caseRun.name}`)
      if (caseRun.failureSummary) {
        lines.push(`  摘要: ${caseRun.failureSummary}`)
      }

      const failedSteps = caseRun.steps.filter(
        (s) => s.status === 'failed' || s.status === 'error'
      )
      for (const step of failedSteps) {
        lines.push(`  Step ${step.stepNo} [${step.type}] ${step.status}: ${step.message}`)
      }
    }
  }

  return lines.join('\n')
}

function formatDurationMs(ms: number | null): string {
  if (ms === null || ms === 0) return '--'
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  return `${minutes}m ${remainSeconds}s`
}

function navigateBackToRuns() {
  void router.push('/runs')
}

function navigateToRepairTarget(path: string, query: Record<string, string | undefined>) {
  void router.push({ path, query })
}

async function copyRunSummary() {
  const detail = runDetail.value
  if (!detail) return

  const text = buildRunSummaryText(detail)
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('执行摘要已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

async function handleRerun() {
  const detail = runDetail.value
  if (!detail) {
    return
  }

  rerunLoading.value = true
  try {
    const newRun = await createTestRun({
      testSuiteId: detail.testSuiteId,
      environmentProfileId: detail.environmentProfileId,
      deviceProfileId: detail.deviceProfileId
    })
    ElMessage.success('已创建重新执行批次，正在跳转…')
    void router.push(`/runs/${newRun.id}`)
  } catch {
    ElMessage.error('重新执行失败，请稍后重试')
  } finally {
    rerunLoading.value = false
  }
}

watch(
  () => route.params.testRunId,
  () => {
    clearPollTimer()
    void loadRunDetail()
  }
)

watch(currentCaseRun, async (caseRun) => {
  await warmupCurrentCaseMedia(caseRun)
})

onMounted(async () => {
  await loadRunDetail()
})

onBeforeUnmount(() => {
  clearPollTimer()
  revokePreviewUrls()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <el-button
        link
        type="primary"
        @click="navigateBackToRuns"
      >
        &larr; 返回执行列表
      </el-button>
    </div>

    <SectionCard
      description="当前页面以 `test-runs`、`case-runs`、`step-results` 三层真实接口做聚合。"
      title="执行总览"
    >
      <template #action>
        <div class="flex items-center gap-3">
          <StatusTag
            v-if="runDetail"
            :status="runDetail.status"
          />
          <el-button
            v-if="runDetail"
            plain
            size="small"
            @click="copyRunSummary"
          >
            复制摘要
          </el-button>
          <el-button
            v-if="runDetail && !ACTIVE_RUN_STATUSES.has(runDetail.status)"
            :loading="rerunLoading"
            color="#2563eb"
            size="small"
            @click="handleRerun"
          >
            重新执行
          </el-button>
        </div>
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
            <p class="m-0 text-sm text-slate-500">套件</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ runDetail.suiteName }}</p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">环境</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ runDetail.environmentName }}</p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">设备</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ runDetail.deviceName }}</p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">创建时间</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ formatDateTime(runDetail.createdAt) }}
            </p>
          </div>
        </div>

        <div
          v-if="repairSummary"
          class="rounded-2xl border border-amber-200 bg-amber-50 p-4"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="m-0 text-sm font-medium text-amber-900">{{ repairSummary.title }}</p>
              <p class="mb-0 mt-2 text-sm leading-6 text-amber-800">
                {{ repairSummary.summary }}
              </p>
              <p class="mb-0 mt-2 text-xs text-amber-700">
                建议动作：返回测试用例页，优先检查失败步骤、断言配置和被引用资源状态。
              </p>
            </div>
            <el-button
              plain
              @click="navigateToRepairTarget(repairSummary.path, repairSummary.query)"
            >
              {{ repairSummary.actionLabel }}
            </el-button>
          </div>
        </div>
      </div>
    </SectionCard>

    <SectionCard
      description="展示执行报告摘要与报告产物，支持截图预览和下载。"
      title="执行报告"
    >
      <div
        v-if="reportLoading"
        class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
      >
        正在加载执行报告...
      </div>

      <div
        v-else-if="runReport"
        class="space-y-6"
      >
        <div class="grid grid-cols-4 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">报告状态</p>
            <div class="mt-3">
              <StatusTag :status="runReport.status" />
            </div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">报告 ID</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">#{{ runReport.id }}</p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">生成时间</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ formatDateTime(runReport.generatedAt) }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">产物数</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ runReport.summary.artifacts.total }}
            </p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div
            v-for="item in reportSummaryCards"
            :key="item.label"
            class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
          >
            <p class="m-0 text-sm text-slate-500">{{ item.label }}</p>
            <p class="mb-0 mt-3 text-sm font-medium text-slate-900 break-all">
              {{ item.value }}
            </p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">失败代码</p>
            <p class="mb-0 mt-3 text-sm font-medium text-slate-900 break-all">
              {{ runReport.summary.failure?.code ?? '--' }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">失败摘要</p>
            <p class="mb-0 mt-3 text-sm font-medium text-slate-900 break-all">
              {{ runReport.summary.failure?.summary ?? runReport.summary.message ?? '--' }}
            </p>
            <el-button
              v-if="repairSummary"
              class="!mt-3"
              plain
              size="small"
              @click="navigateToRepairTarget(repairSummary.path, repairSummary.query)"
            >
              {{ repairSummary.actionLabel }}
            </el-button>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">开始时间</p>
            <p class="mb-0 mt-3 text-sm font-medium text-slate-900 break-all">
              {{ runReport.summary.timing.startedAt ? formatDateTime(runReport.summary.timing.startedAt) : '--' }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">总耗时</p>
            <p class="mb-0 mt-3 text-sm font-medium text-slate-900 break-all">
              {{ runReport.summary.timing.durationMs !== null ? `${runReport.summary.timing.durationMs} ms` : '--' }}
            </p>
          </div>
        </div>

        <div
          v-if="reportArtifactTypeEntries.length > 0"
          class="grid grid-cols-4 gap-4"
        >
          <div
            v-for="[artifactType, count] in reportArtifactTypeEntries"
            :key="artifactType"
            class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
          >
            <p class="m-0 text-sm text-slate-500">{{ artifactType }}</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ count }}</p>
          </div>
        </div>

        <div>
          <h4 class="mb-4 mt-0 text-base font-semibold text-slate-900">报告产物</h4>
          <div
            v-if="reportArtifacts.length > 0"
            class="grid grid-cols-3 gap-4"
          >
            <div
              v-for="artifact in reportArtifacts"
              :key="artifact.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="mb-3 flex items-center justify-between">
                <p class="m-0 font-medium text-slate-900">
                  {{ artifact.artifactType }}
                </p>
                <el-button
                  v-if="artifact.mediaObjectId"
                  link
                  size="small"
                  type="primary"
                  @click="void downloadMedia(artifact.mediaObjectId)"
                >
                  下载
                </el-button>
              </div>

              <img
                v-if="artifact.mediaObjectId && mediaPreviewMap[artifact.mediaObjectId]"
                :src="mediaPreviewMap[artifact.mediaObjectId]"
                class="mb-3 h-40 w-full rounded-xl border border-slate-200 object-cover"
                :alt="artifact.artifactType"
              />

              <div
                v-else
                class="mb-3 flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-400"
              >
                {{ artifact.mediaObjectId && mediaLoadingMap[artifact.mediaObjectId] ? '媒体加载中...' : '暂无可预览图片' }}
              </div>

              <div class="space-y-2">
                <div class="rounded-lg bg-white p-2 border border-slate-200">
                  <p class="m-0 text-xs text-slate-500">
                    <span class="font-medium">产物来源</span>
                  </p>
                  <p
                    v-if="artifact.caseRunId !== null"
                    class="mb-0 mt-1 text-xs text-slate-700"
                  >
                    用例执行：case-run #{{ artifact.caseRunId }}
                  </p>
                  <p
                    v-if="artifact.stepResultId !== null"
                    class="mb-0 mt-1 text-xs text-slate-700"
                  >
                    步骤结果：step-result #{{ artifact.stepResultId }}
                  </p>
                  <p
                    v-if="artifact.mediaObjectId !== null"
                    class="mb-0 mt-1 text-xs text-slate-400"
                  >
                    媒体对象：#{{ artifact.mediaObjectId }}
                  </p>
                </div>
                <p class="mb-0 text-xs text-slate-400">
                  生成时间：{{ formatDateTime(artifact.createdAt) }}
                </p>
              </div>
            </div>
          </div>

          <el-empty
            v-else
            description="当前执行尚未生成报告产物"
          />
        </div>
      </div>

      <el-empty
        v-else
        description="当前执行尚未生成报告"
      />
    </SectionCard>

    <div class="grid grid-cols-[440px_minmax(0,1fr)] gap-6">
      <SectionCard
        description="点击某个 case-run 可查看对应步骤执行结果。"
        title="用例执行实例"
      >
        <el-table
          v-loading="loading"
          :data="runDetail?.caseRuns ?? []"
          :default-sort="{ prop: 'durationMs', order: 'descending' }"
          highlight-current-row
          stripe
          @row-click="selectCaseRun"
        >
          <el-table-column label="用例名称" min-width="180" prop="name" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="耗时" prop="durationMs" sortable width="110">
            <template #default="{ row }">
              {{ formatDurationMs(row.durationMs) }}
            </template>
          </el-table-column>
          <el-table-column label="Diff" prop="diffCount" width="80" />
        </el-table>
      </SectionCard>

      <SectionCard
        description="step-results 展示真实执行步骤，并补充截图、Diff 图和下载入口。"
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

                <div
                  v-if="getStepMediaEntries(step).length > 0"
                  class="mt-4"
                >
                  <p class="mb-3 text-sm font-medium text-slate-700">图片对照</p>
                  <div class="grid grid-cols-3 gap-3">
                    <div
                      v-for="entry in getStepMediaEntries(step)"
                      :key="`${step.id}-${entry.label}`"
                      class="rounded-2xl border border-slate-200 bg-slate-50 p-3"
                    >
                      <div class="mb-2 flex items-center justify-between">
                        <p class="m-0 text-sm font-medium text-slate-900">
                          {{ entry.label }}
                        </p>
                        <el-button
                          link
                          size="small"
                          type="primary"
                          @click="void downloadMedia(entry.mediaObjectId)"
                        >
                          下载
                        </el-button>
                      </div>

                      <img
                        v-if="mediaPreviewMap[entry.mediaObjectId]"
                        :src="mediaPreviewMap[entry.mediaObjectId]"
                        :alt="entry.label"
                        class="h-48 w-full rounded-xl border border-slate-200 object-contain bg-white"
                      />

                      <div
                        v-else
                        class="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-400"
                      >
                        {{ mediaLoadingMap[entry.mediaObjectId] ? '加载中...' : (mediaErrorMap[entry.mediaObjectId] || '暂无预览') }}
                      </div>

                      <p class="mb-0 mt-2 text-xs text-slate-400">
                        media #{{ entry.mediaObjectId }}
                      </p>
                    </div>
                  </div>
                </div>

                <p
                  v-else-if="step.artifactLabel"
                  class="mb-0 mt-3 text-xs uppercase tracking-wide text-slate-400"
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
