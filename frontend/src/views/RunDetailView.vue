<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import OcrEvidencePanel from '@/components/OcrEvidencePanel.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getMediaObject, getMediaObjectContent } from '@/api/modules/mediaObjects'
import {
  cancelTestRun,
  createTestRun,
  getRunDetail,
  getTestRunReport,
  listReportArtifacts,
  rerunFailedCases
} from '@/api/modules/testRuns'
import { ApiError } from '@/api/client'
import { formatDateTime } from '@/utils/format'
import {
  getReportConclusion,
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

interface MediaPreviewItem {
  mediaObjectId: number
  title: string
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const reportLoading = ref(false)
const rerunLoading = ref(false)
const rerunFailedLoading = ref(false)
const cancelLoading = ref(false)
const runDetail = ref<RunDetail | null>(null)
const runReport = ref<RunReport | null>(null)
const reportArtifacts = ref<ReportArtifact[]>([])
const selectedCaseRunId = ref<number | null>(null)

const mediaObjectMap = ref<Record<number, MediaObject>>({})
const mediaPreviewMap = ref<Record<number, string>>({})
const mediaLoadingMap = ref<Record<number, boolean>>({})
const mediaErrorMap = ref<Record<number, string>>({})
const imagePreviewVisible = ref(false)
const imagePreviewItems = ref<MediaPreviewItem[]>([])
const imagePreviewIndex = ref(0)

let pollTimer: number | null = null

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling'])

const currentPreviewItem = computed(() => {
  return imagePreviewItems.value[imagePreviewIndex.value] ?? null
})

const imagePreviewTitle = computed(() => currentPreviewItem.value?.title ?? '')

const imagePreviewUrl = computed(() => {
  const mediaObjectId = currentPreviewItem.value?.mediaObjectId
  return mediaObjectId ? mediaPreviewMap.value[mediaObjectId] ?? '' : ''
})

const canPreviewPrevious = computed(() => imagePreviewIndex.value > 0)
const canPreviewNext = computed(() => imagePreviewIndex.value < imagePreviewItems.value.length - 1)

const currentCaseRun = computed(() => {
  return runDetail.value?.caseRuns.find((item) => item.id === selectedCaseRunId.value) ?? null
})

const repairSummary = computed(() => {
  if (!runDetail.value || !['failed', 'partial_failed', 'error'].includes(runDetail.value.status)) {
    return null
  }
  const repairTarget = resolveRunRepairTarget(
    runDetail.value,
    runReport.value?.summary.failure
  )
  if (!repairTarget) {
    return null
  }

  return {
    title:
      repairTarget.kind === 'system'
        ? '平台运行环境异常'
        : `建议修复：${repairTarget.resourceName || repairTarget.caseRunName}`,
    summary: repairTarget.failureSummary,
    actionLabel: repairTarget.label,
    kind: repairTarget.kind,
    resourceName: repairTarget.resourceName,
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
      hint: '本次执行纳入的全部用例。'
    },
    {
      label: '通过用例',
      value: runDetail.value.summary.passedCases,
      hint: '完成执行且结果符合预期。'
    },
    {
      label: '失败用例',
      value: runDetail.value.summary.failedCases,
      hint: '断言未通过的用例数量。'
    },
    {
      label: '执行耗时',
      value: `${runDetail.value.summary.durationSeconds}s`,
      hint: '从开始到结束的总耗时。'
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

const reportConclusion = computed(() => {
  if (!runReport.value) {
    return ''
  }

  return getReportConclusion(
    runReport.value.status,
    runReport.value.summary.failure
  )
})

const reportArtifactTypeEntries = computed(() => {
  if (!runReport.value) {
    return []
  }

  return Object.entries(runReport.value.summary.artifacts.byType)
})

function clearPollTimer() {
  // Stops the active detail polling loop, if one is running.
  if (pollTimer === null) {
    return
  }

  window.clearTimeout(pollTimer)
  pollTimer = null
}

function shouldPollRunDetail(detail: RunDetail) {
  // @param detail Current run detail snapshot.
  // @returns True while the run is still in an active status that can change server-side.
  return ACTIVE_RUN_STATUSES.has(detail.status)
}

function scheduleRunDetailRefresh() {
  // Schedules the next silent refresh while the run is still progressing.
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
      label: step.resultMetadata.ocr ? 'OCR 标注图' : '实际截图',
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

function buildStepPreviewGroup(step: StepResult): MediaPreviewItem[] {
  return getStepMediaEntries(step).map((entry) => ({
    mediaObjectId: entry.mediaObjectId,
    title: `${step.name} · ${entry.label}`
  }))
}

function buildReportPreviewGroup(artifacts: ReportArtifact[]): MediaPreviewItem[] {
  return artifacts
    .filter((artifact): artifact is ReportArtifact & { mediaObjectId: number } => artifact.mediaObjectId !== null)
    .map((artifact) => ({
      mediaObjectId: artifact.mediaObjectId,
      title: artifact.artifactType
    }))
}

async function ensureMediaLoaded(mediaObjectId: number) {
  // @param mediaObjectId Media object that should be available for preview/download.
  // @returns Resolves once preview metadata and blob URL are cached, or no-op if already loading/loaded.
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
  // @param caseRun Currently selected case run whose step media should be preloaded for fast preview.
  if (!caseRun) {
    return
  }

  const mediaIds = caseRun.steps.flatMap((step) =>
    getStepMediaEntries(step).map((item) => item.mediaObjectId)
  )

  await Promise.all(mediaIds.map((mediaObjectId) => ensureMediaLoaded(mediaObjectId)))
}

async function warmupReportArtifactMedia(artifacts: ReportArtifact[]) {
  // @param artifacts Report artifacts whose media previews should be prefetched.
  const mediaIds = artifacts
    .map((item) => item.mediaObjectId)
    .filter((item): item is number => item !== null)

  await Promise.all(mediaIds.map((mediaObjectId) => ensureMediaLoaded(mediaObjectId)))
}

async function loadRunReport(testRunId: number) {
  // @param testRunId Test run whose report summary and report artifacts should be loaded.
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
  // @param testRunId Test run whose report state should stay aligned with the detail view.
  // @param detail Latest run detail snapshot used to decide whether report polling is meaningful yet.
  if (shouldPollRunDetail(detail) && runReport.value === null) {
    reportArtifacts.value = []
    return
  }

  await loadRunReport(testRunId)
}

async function loadRunDetail(options: { silent?: boolean } = {}) {
  // @param options.silent When true, refresh in place without showing the page-level loading skeleton.
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

async function openMediaPreview(
  mediaObjectId: number,
  title: string,
  group: MediaPreviewItem[] = [{ mediaObjectId, title }]
) {
  // @param mediaObjectId Media object that should be focused first in the preview dialog.
  // @param title Default preview title for single-item preview flows.
  // @param group Optional preview group so users can browse related media within one dialog.
  try {
    await Promise.all(group.map((item) => ensureMediaLoaded(item.mediaObjectId)))
    const url = mediaPreviewMap.value[mediaObjectId]
    if (!url) {
      ElMessage.error(mediaErrorMap.value[mediaObjectId] || '当前媒体尚未加载完成。')
      return
    }

    imagePreviewItems.value = group
    imagePreviewIndex.value = Math.max(
      0,
      group.findIndex((item) => item.mediaObjectId === mediaObjectId)
    )
    imagePreviewVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '预览加载失败，请稍后重试。')
  }
}

function closeMediaPreview() {
  imagePreviewVisible.value = false
  imagePreviewItems.value = []
  imagePreviewIndex.value = 0
}

function previewPrevious() {
  if (!canPreviewPrevious.value) {
    return
  }
  imagePreviewIndex.value -= 1
}

function previewNext() {
  if (!canPreviewNext.value) {
    return
  }
  imagePreviewIndex.value += 1
}

async function downloadCurrentPreviewMedia() {
  const mediaObjectId = currentPreviewItem.value?.mediaObjectId
  if (!mediaObjectId) {
    return
  }
  await downloadMedia(mediaObjectId)
}

function selectCaseRun(caseRun: CaseRun) {
  selectedCaseRunId.value = caseRun.id
}

function buildRunSummaryText(detail: RunDetail): string {
  // @param detail Run detail snapshot to turn into a copy-friendly summary string.
  const effectiveCases =
    detail.summary.passedCases + detail.summary.failedCases + detail.summary.errorCases
  const passRate = effectiveCases > 0
    ? `${Math.round((detail.summary.passedCases / effectiveCases) * 100)}%`
    : '--'

  const lines: string[] = [
    `[执行摘要] 批次 #${detail.id}`,
    `套件: ${detail.suiteName}`,
    `环境: ${detail.environmentName} | 设备: ${detail.deviceName}`,
    `状态: ${detail.status} | 通过率: ${passRate} (${detail.summary.passedCases}/${effectiveCases})`,
    `耗时: ${detail.summary.durationSeconds}s | 创建: ${formatDateTime(detail.createdAt)}`
  ]

  const failedCases = detail.caseRuns.filter(
    (c) => c.status === 'failed' || c.status === 'error'
  )

  if (failedCases.length > 0) {
    lines.push('', `--- 失败用例 (${failedCases.length}) ---`)

    for (const caseRun of failedCases) {
      lines.push(``, `[${caseRun.status.toUpperCase()}] ${caseRun.name}`)
      lines.push(`  摘要: ${formatCaseRunSummary(caseRun)}`)

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
  // @param path Target route returned by run-failure repair resolution.
  // @param query Query params that preserve failure context in the repair page.
  void router.push({ path, query })
}

function handlePrimaryRepairAction() {
  if (!repairSummary.value) return
  if (repairSummary.value.kind === 'system' || !repairSummary.value.path) {
    void handleRerun()
    return
  }
  navigateToRepairTarget(repairSummary.value.path, repairSummary.value.query)
}

function formatStepType(type: string) {
  const labelMap: Record<string, string> = {
    navigate: '打开页面',
    click: '点击',
    input: '输入',
    wait: '等待',
    screenshot: '截图',
    template_assert: '视觉断言',
    ocr_assert: '文字断言',
    component_call: '调用公共组件'
  }
  return labelMap[type] ?? type
}

function formatArtifactType(type: string) {
  const labelMap: Record<string, string> = {
    run_screenshot: '执行截图',
    actual_screenshot: '实际截图',
    expected_screenshot: '基准图',
    diff_image: '差异图',
    ocr_annotated_image: 'OCR 标注图'
  }
  return labelMap[type] ?? '执行产物'
}

function formatCaseRunSummary(caseRun: CaseRun) {
  if (caseRun.status === 'failed') return '用例断言未通过，请查看失败步骤与证据。'
  if (caseRun.status === 'error') return '用例执行异常，本次验证未正常完成。'
  if (caseRun.status === 'cancelled') return '用例已取消。'
  return '用例执行完成。'
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
  // Recreates a new run from the same suite/environment/device combination as the current run.
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

async function handleRerunFailed() {
  // Creates a new run containing only failed/errored cases from the current batch.
  const detail = runDetail.value
  if (!detail) {
    return
  }

  rerunFailedLoading.value = true
  try {
    const newRun = await rerunFailedCases(detail.id)
    ElMessage.success('重跑批次已创建，正在跳转…')
    void router.push(`/runs/${newRun.id}`)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'NO_FAILED_CASES_TO_RERUN') {
      ElMessage.warning('该批次无失败用例，无需重跑')
    } else {
      ElMessage.error('重跑失败，请稍后重试')
    }
  } finally {
    rerunFailedLoading.value = false
  }
}

async function handleCancelRun() {
  // Requests server-side cancellation; the detail page keeps polling until the terminal status settles.
  const detail = runDetail.value
  if (!detail) {
    return
  }

  try {
    await ElMessageBox.confirm(
      '取消后正在执行的用例将中止，已完成的用例结果将保留。',
      '确认取消执行',
      { confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning' }
    )
  } catch {
    return
  }

  cancelLoading.value = true
  try {
    await cancelTestRun(detail.id)
    ElMessage.success('执行批次已标记为取消中')
  } catch (error) {
    if (error instanceof ApiError && error.code === 'TEST_RUN_STATUS_CONFLICT') {
      ElMessage.warning('该批次状态已变更，无法取消')
    } else {
      ElMessage.error('取消执行失败，请稍后重试')
    }
  } finally {
    cancelLoading.value = false
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
      :description="runDetail ? `${runDetail.environmentName} · ${runDetail.deviceName}` : '正在加载执行结果'"
      :title="runDetail ? `${runDetail.suiteName} · 执行结果` : '执行结果'"
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
            v-if="runDetail && (runDetail.status === 'queued' || runDetail.status === 'running')"
            :loading="cancelLoading"
            plain
            size="small"
            type="danger"
            @click="handleCancelRun"
          >
            取消执行
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
          <el-button
            v-if="runDetail && !ACTIVE_RUN_STATUSES.has(runDetail.status) && (runDetail.summary.failedCases > 0 || runDetail.summary.errorCases > 0)"
            :loading="rerunFailedLoading"
            plain
            size="small"
            type="warning"
            @click="handleRerunFailed"
          >
            重跑失败项
          </el-button>
        </div>
      </template>

      <div
        v-if="runDetail"
        class="space-y-6"
      >
        <div class="grid grid-cols-2 gap-4 2xl:grid-cols-4">
          <MetricCard
            v-for="metric in metrics"
            :key="metric.label"
            :hint="metric.hint"
            :label="metric.label"
            :value="metric.value"
          />
        </div>

        <div class="grid grid-cols-2 gap-4 2xl:grid-cols-4">
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
          <div class="flex flex-col items-start justify-between gap-4 lg:flex-row">
            <div class="min-w-0">
              <p class="m-0 text-sm font-medium text-amber-900">{{ repairSummary.title }}</p>
              <p class="mb-0 mt-2 text-sm leading-6 text-amber-800">
                {{ repairSummary.summary }}
              </p>
              <p class="mb-0 mt-2 text-xs text-amber-700">
                责任资源：{{ repairSummary.resourceName || '请查看执行证据' }}
              </p>
            </div>
            <el-button
              plain
              @click="handlePrimaryRepairAction"
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
        <div class="grid grid-cols-2 gap-4 2xl:grid-cols-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">报告状态</p>
            <div class="mt-3">
              <StatusTag :status="runReport.status" />
            </div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">责任资源</p>
            <p class="mb-0 mt-3 break-words text-lg font-semibold text-slate-900">
              {{ repairSummary?.resourceName || '无需处理' }}
            </p>
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

        <div class="grid grid-cols-2 gap-4 2xl:grid-cols-4">
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

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:col-span-1">
            <p class="m-0 text-sm text-slate-500">执行结论</p>
            <p class="mb-0 mt-3 break-words text-sm font-medium leading-6 text-slate-900">
              {{ reportConclusion }}
            </p>
            <el-button
              v-if="repairSummary"
              class="!mt-3"
              plain
              size="small"
              @click="handlePrimaryRepairAction"
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

        <details class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <summary class="cursor-pointer text-sm font-medium text-slate-700">技术详情</summary>
          <div class="mt-4 grid grid-cols-1 gap-3 text-xs text-slate-600 md:grid-cols-2">
            <p class="m-0 break-all">报告 ID：#{{ runReport.id }}</p>
            <p class="m-0 break-all">错误码：{{ runReport.summary.failure?.code ?? '--' }}</p>
            <p class="m-0 break-all md:col-span-2">
              原始信息：{{ runReport.summary.failure?.summary ?? runReport.summary.message ?? '--' }}
            </p>
          </div>
        </details>

        <div
          v-if="reportArtifactTypeEntries.length > 0"
          class="grid grid-cols-2 gap-4 2xl:grid-cols-4"
        >
          <div
            v-for="[artifactType, count] in reportArtifactTypeEntries"
            :key="artifactType"
            class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
          >
            <p class="m-0 text-sm text-slate-500">{{ formatArtifactType(artifactType) }}</p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ count }}</p>
          </div>
        </div>

        <div>
          <h4 class="mb-4 mt-0 text-base font-semibold text-slate-900">报告产物</h4>
          <div
            v-if="reportArtifacts.length > 0"
            class="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3"
          >
            <div
              v-for="artifact in reportArtifacts"
              :key="artifact.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="mb-3 flex items-center justify-between">
                <p class="m-0 font-medium text-slate-900">
                  {{ formatArtifactType(artifact.artifactType) }}
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
                class="mb-3 h-40 w-full cursor-zoom-in rounded-xl border border-slate-200 object-cover transition hover:border-blue-300 hover:shadow-md"
                :alt="artifact.artifactType"
                @click="void openMediaPreview(artifact.mediaObjectId, artifact.artifactType, buildReportPreviewGroup(reportArtifacts))"
              />

              <div
                v-else
                class="mb-3 flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-400"
              >
                {{ artifact.mediaObjectId && mediaLoadingMap[artifact.mediaObjectId] ? '媒体加载中...' : '暂无可预览图片' }}
              </div>

              <div class="space-y-2">
                <details class="rounded-lg border border-slate-200 bg-white p-2">
                  <summary class="cursor-pointer text-xs font-medium text-slate-500">技术详情</summary>
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
                </details>
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

    <div class="grid grid-cols-1 gap-6 2xl:grid-cols-[440px_minmax(0,1fr)]">
      <SectionCard
        description="选择一个用例查看步骤结果与证据。"
        title="用例结果"
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
        description="按业务步骤查看状态、耗时和截图证据。"
        title="步骤结果"
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
              结果摘要：{{ formatCaseRunSummary(currentCaseRun) }}
            </p>
            <details
              v-if="currentCaseRun.failureSummary && (currentCaseRun.status === 'failed' || currentCaseRun.status === 'error')"
              class="mt-3 rounded-xl border border-slate-200 bg-white p-3"
            >
              <summary class="cursor-pointer text-xs font-medium text-slate-600">技术详情</summary>
              <p class="mb-0 mt-2 break-all text-xs leading-5 text-slate-500">
                {{ currentCaseRun.failureSummary }}
              </p>
            </details>
          </div>

          <el-timeline>
            <el-timeline-item
              v-for="step in currentCaseRun.steps"
              :key="step.id"
              :timestamp="`步骤 ${step.stepNo}`"
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
                  类型：{{ formatStepType(step.type) }} · 耗时：{{ step.durationMs ?? 0 }} ms
                </p>
                <details
                  v-if="step.technicalMessage"
                  class="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3"
                >
                  <summary class="cursor-pointer text-xs font-medium text-slate-600">技术详情</summary>
                  <p class="mb-0 mt-2 break-all text-xs leading-5 text-slate-500">
                    {{ step.technicalMessage }}
                  </p>
                </details>

                <OcrEvidencePanel
                  v-if="step.resultMetadata.ocr"
                  :metadata="step.resultMetadata.ocr"
                />

                <div
                  v-if="getStepMediaEntries(step).length > 0"
                  class="mt-4"
                >
                  <p class="mb-3 text-sm font-medium text-slate-700">图片对照</p>
                  <div class="grid grid-cols-1 gap-3 xl:grid-cols-3">
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
                        class="h-48 w-full cursor-zoom-in rounded-xl border border-slate-200 bg-white object-contain transition hover:border-blue-300 hover:shadow-md"
                        @click="void openMediaPreview(entry.mediaObjectId, `${step.name} · ${entry.label}`, buildStepPreviewGroup(step))"
                      />

                      <div
                        v-else
                        class="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-400"
                      >
                        {{ mediaLoadingMap[entry.mediaObjectId] ? '加载中...' : (mediaErrorMap[entry.mediaObjectId] || '暂无预览') }}
                      </div>

                      <details class="mt-2 text-xs text-slate-400">
                        <summary class="cursor-pointer">技术详情</summary>
                        <p class="mb-0 mt-1">媒体对象：#{{ entry.mediaObjectId }}</p>
                      </details>
                    </div>
                  </div>
                </div>

                <p
                  v-else-if="step.artifactLabel"
                  class="mb-0 mt-3 text-xs text-slate-400"
                >
                  {{ step.artifactLabel }}
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

  <el-dialog
    v-model="imagePreviewVisible"
    :title="imagePreviewTitle || '图片预览'"
    append-to-body
    destroy-on-close
    top="4vh"
    width="min(92vw, 1200px)"
    @closed="closeMediaPreview"
  >
    <div class="mb-3 flex items-center justify-between gap-3 text-xs text-slate-500">
      <span>
        {{ currentPreviewItem?.title ?? '未选择图片' }}
      </span>
      <span v-if="imagePreviewItems.length > 1">
        {{ imagePreviewIndex + 1 }} / {{ imagePreviewItems.length }}
      </span>
    </div>

    <div class="flex max-h-[78vh] items-center justify-center gap-3 overflow-auto rounded-2xl bg-slate-950/95 p-4">
      <el-button
        :disabled="!canPreviewPrevious"
        circle
        plain
        @click="previewPrevious"
      >
        ‹
      </el-button>

      <img
        v-if="imagePreviewUrl"
        :src="imagePreviewUrl"
        :alt="imagePreviewTitle || '图片预览'"
        class="max-h-[72vh] max-w-full rounded-xl object-contain"
      >

      <el-button
        :disabled="!canPreviewNext"
        circle
        plain
        @click="previewNext"
      >
        ›
      </el-button>
    </div>
    <template #footer>
      <div class="flex items-center justify-between gap-3">
        <p class="m-0 text-xs text-slate-400">支持点击缩略图查看大图预览，当前组内可左右切换并直接下载。</p>
        <div class="flex items-center gap-2">
          <el-button :disabled="!currentPreviewItem" plain @click="void downloadCurrentPreviewMedia()">下载当前图片</el-button>
          <el-button @click="closeMediaPreview">关闭</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>
