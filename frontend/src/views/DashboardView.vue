<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listEnvironmentProfiles } from '@/api/modules/environments'
import { listTemplates } from '@/api/modules/templates'
import { listTestCases } from '@/api/modules/testCases'
import { listTestRuns } from '@/api/modules/testRuns'
import { listTestSuites } from '@/api/modules/testSuites'
import { useWorkspaceStore } from '@/stores/workspace'
import { formatDateTime } from '@/utils/format'
import type {
  EnvironmentProfile,
  Template,
  TestCase,
  TestRun,
  TestSuite
} from '@/types/models'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const templates = ref<Template[]>([])
const testCases = ref<TestCase[]>([])
const testSuites = ref<TestSuite[]>([])
const testRuns = ref<TestRun[]>([])
const environmentProfiles = ref<EnvironmentProfile[]>([])

const summaryMetrics = computed(() => {
  const recentRun = testRuns.value[0]
  const attentionRuns = testRuns.value.filter((item) => {
    return item.status === 'failed' || item.status === 'partial_failed'
  }).length

  return [
    {
      label: '当前工作空间',
      value: workspaceStore.currentWorkspace?.name ?? '未选择',
      hint: '通过工作空间上下文隔离资源与执行数据。'
    },
    {
      label: '模板总数',
      value: templates.value.length,
      hint: '映射 `templates` 与 `baseline-revisions` 的核心资产。'
    },
    {
      label: '活跃套件',
      value: testSuites.value.filter((item) => item.status === 'active').length,
      hint: 'MVP 以可手动触发的回归套件为主。'
    },
    {
      label: '最近执行',
      value: recentRun ? formatDateTime(recentRun.createdAt) : '暂无',
      hint: '从最近一个 `test-runs` 批次读取。'
    },
    {
      label: '待关注批次',
      value: attentionRuns,
      hint: '统计 failed 与 partial_failed 状态。'
    }
  ]
})

const recentRuns = computed(() => testRuns.value.slice(0, 3))

const quickActions = [
  {
    title: '配置环境',
    description: '先准备 baseUrl、变量与设备预设，再进入回归执行。',
    path: '/environments',
    buttonText: '进入环境配置'
  },
  {
    title: '维护模板',
    description: '查看基准版本与忽略区域比例，确保视觉比对口径稳定。',
    path: '/templates',
    buttonText: '进入模板管理'
  },
  {
    title: '触发执行',
    description: '从套件页手动创建一次 test-run，验证 MVP 闭环。',
    path: '/suites',
    buttonText: '进入套件管理'
  }
] as const

const releaseReadiness = computed(() => {
  const publishedCases = testCases.value.filter((item) => item.status === 'published').length
  const draftCases = testCases.value.length - publishedCases
  const publishedTemplates = templates.value.filter((item) => item.status === 'published').length
  const activeEnvironments = environmentProfiles.value.filter((item) => item.status === 'active').length

  return [
    {
      label: '激活模板',
      value: `${publishedTemplates}/${templates.value.length || 0}`,
      hint: '当前以前端可见状态汇总模板可用性。'
    },
    {
      label: '已发布用例',
      value: `${publishedCases}/${testCases.value.length || 0}`,
      hint: '当前展示仍以 `published` 作为稳定执行近似口径。'
    },
    {
      label: '草稿用例',
      value: draftCases,
      hint: '需要继续补齐断言或组件复用。'
    },
    {
      label: '可用环境',
      value: activeEnvironments,
      hint: '至少保留一个稳定联调环境。'
    }
  ]
})

const executionTrend = computed(() => {
  const recent10 = testRuns.value.slice(0, 10)
  const passedCount = recent10.filter((item) => item.status === 'passed').length
  const failedCount = recent10.filter((item) => item.status === 'failed' || item.status === 'partial_failed').length
  const passRate = recent10.length > 0 ? Math.round((passedCount / recent10.length) * 100) : 0

  return {
    total: recent10.length,
    passed: passedCount,
    failed: failedCount,
    passRate
  }
})

const pendingTemplates = computed(() => {
  return templates.value.filter((item) =>
    item.status === 'draft' || item.currentBaselineRevisionId === null
  )
})

const riskAlerts = computed(() => {
  const alerts: Array<{ type: 'warning' | 'error'; message: string }> = []

  if (environmentProfiles.value.filter((item) => item.status === 'active').length === 0) {
    alerts.push({ type: 'error', message: '无可用环境配置，无法触发执行' })
  }

  if (testSuites.value.filter((item) => item.status === 'active').length === 0) {
    alerts.push({ type: 'warning', message: '无活跃套件，建议至少维护一个回归套件' })
  }

  if (pendingTemplates.value.length > 5) {
    alerts.push({ type: 'warning', message: `${pendingTemplates.value.length} 个模板待处理，可能影响断言稳定性` })
  }

  const recentFailedRuns = testRuns.value.slice(0, 5).filter((item) =>
    item.status === 'failed' || item.status === 'partial_failed'
  )
  if (recentFailedRuns.length >= 3) {
    alerts.push({ type: 'error', message: '最近 5 次执行中有 3 次及以上失败，需要排查' })
  }

  return alerts
})

onMounted(async () => {
  loading.value = true
  try {
    const [templateItems, caseItems, suiteItems, runItems, environmentItems] =
      await Promise.all([
        listTemplates(),
        listTestCases(),
        listTestSuites(),
        listTestRuns(),
        listEnvironmentProfiles()
      ])

    templates.value = templateItems
    testCases.value = caseItems
    testSuites.value = suiteItems
    testRuns.value = runItems
    environmentProfiles.value = environmentItems
  } finally {
    loading.value = false
  }
})

function navigate(path: string) {
  void router.push(path)
}
</script>

<template>
  <div class="space-y-6">
    <div
      v-if="riskAlerts.length > 0"
      class="rounded-2xl border-2 border-orange-200 bg-orange-50 p-4"
    >
      <h3 class="m-0 mb-3 text-base font-semibold text-orange-900">⚠️ 风险提示</h3>
      <div class="space-y-2">
        <div
          v-for="(alert, index) in riskAlerts"
          :key="index"
          class="flex items-start gap-2 text-sm"
          :class="alert.type === 'error' ? 'text-red-700' : 'text-orange-700'"
        >
          <span class="font-medium">{{ alert.type === 'error' ? '🔴' : '🟡' }}</span>
          <span>{{ alert.message }}</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-5 gap-4">
      <MetricCard
        v-for="metric in summaryMetrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <div class="grid grid-cols-2 gap-6">
      <SectionCard
        description="最近 10 次执行的通过率趋势。"
        title="执行趋势"
      >
        <div class="grid grid-cols-3 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">总执行次数</p>
            <p class="mb-0 mt-3 text-2xl font-semibold text-slate-900">{{ executionTrend.total }}</p>
          </div>
          <div class="rounded-2xl border border-green-200 bg-green-50 p-4">
            <p class="m-0 text-sm text-green-700">通过次数</p>
            <p class="mb-0 mt-3 text-2xl font-semibold text-green-900">{{ executionTrend.passed }}</p>
          </div>
          <div class="rounded-2xl border border-red-200 bg-red-50 p-4">
            <p class="m-0 text-sm text-red-700">失败次数</p>
            <p class="mb-0 mt-3 text-2xl font-semibold text-red-900">{{ executionTrend.failed }}</p>
          </div>
        </div>
        <div class="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4">
          <p class="m-0 text-sm text-blue-700">通过率</p>
          <p class="mb-0 mt-3 text-3xl font-bold text-blue-900">{{ executionTrend.passRate }}%</p>
        </div>
      </SectionCard>

      <SectionCard
        description="需要补充基准版本或发布的模板资产。"
        title="待处理模板"
      >
        <div
          v-if="pendingTemplates.length > 0"
          class="space-y-2 max-h-64 overflow-y-auto"
        >
          <div
            v-for="template in pendingTemplates.slice(0, 8)"
            :key="template.id"
            class="rounded-2xl border border-slate-200 bg-slate-50 p-3"
          >
            <div class="flex items-center justify-between">
              <p class="m-0 text-sm font-medium text-slate-900">{{ template.name }}</p>
              <StatusTag :status="template.status" size="small" />
            </div>
            <p class="mb-0 mt-1 text-xs text-slate-500">
              {{ template.currentBaselineRevisionId === null ? '缺少基准版本' : '草稿状态' }}
            </p>
          </div>
          <p
            v-if="pendingTemplates.length > 8"
            class="mb-0 mt-2 text-xs text-slate-400 text-center"
          >
            还有 {{ pendingTemplates.length - 8 }} 个模板待处理
          </p>
        </div>
        <el-empty
          v-else
          description="所有模板均已就绪"
        />
      </SectionCard>
    </div>

    <div class="grid grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] gap-6">
      <SectionCard
        description="从工作台快速进入 MVP 主路径，减少多页面跳转成本。"
        title="快捷操作"
      >
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div
            v-for="action in quickActions"
            :key="action.path"
            class="rounded-3xl border border-slate-200 bg-slate-50 p-5"
          >
            <h3 class="m-0 text-lg font-semibold text-slate-900">
              {{ action.title }}
            </h3>
            <p class="mb-0 mt-3 text-sm leading-7 text-slate-500">
              {{ action.description }}
            </p>
            <el-button
              class="!mt-5"
              plain
              type="primary"
              @click="navigate(action.path)"
            >
              {{ action.buttonText }}
            </el-button>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        description="从最近执行批次快速下钻到执行详情。"
        title="最近执行"
      >
        <div
          v-loading="loading"
          class="space-y-3"
        >
          <button
            v-for="run in recentRuns"
            :key="run.id"
            class="w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left transition hover:border-slate-300"
            type="button"
            @click="navigate(`/runs/${run.id}`)"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="m-0 text-base font-semibold text-slate-900">
                  {{ run.suiteName }}
                </p>
                <p class="mb-0 mt-2 text-sm text-slate-500">
                  {{ run.environmentName }} · {{ run.deviceName }}
                </p>
              </div>
              <StatusTag :status="run.status" />
            </div>
            <p class="mb-0 mt-3 text-xs text-slate-400">
              {{ formatDateTime(run.createdAt) }}
            </p>
          </button>
          <el-empty
            v-if="recentRuns.length === 0 && !loading"
            description="暂无执行记录"
          />
        </div>
      </SectionCard>
    </div>

    <div class="grid grid-cols-[minmax(0,1fr)_360px] gap-6">
      <SectionCard
        description="面向 MVP 上线前的基础 readiness 检查。"
        title="发布就绪度"
      >
        <div class="grid grid-cols-4 gap-4">
          <div
            v-for="item in releaseReadiness"
            :key="item.label"
            class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
          >
            <p class="m-0 text-sm text-slate-500">
              {{ item.label }}
            </p>
            <p class="mb-0 mt-3 text-2xl font-semibold text-slate-900">
              {{ item.value }}
            </p>
            <p class="mb-0 mt-2 text-sm text-slate-400">
              {{ item.hint }}
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        description="以当前工作空间上下文展示边界信息。"
        title="空间摘要"
      >
        <div class="space-y-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              工作空间编码
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ workspaceStore.currentWorkspace?.code ?? '--' }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              成员规模
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ workspaceStore.currentWorkspace?.memberCount ?? 0 }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              当前角色
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ workspaceStore.currentWorkspace?.role ?? '--' }}
            </p>
          </div>
        </div>
      </SectionCard>
    </div>
  </div>
</template>
