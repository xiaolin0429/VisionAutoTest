<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import { listComponents } from '@/api/modules/components'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { getTestCaseDetail } from '@/api/modules/testCases'
import { getTestSuiteDetail, listTestSuites } from '@/api/modules/testSuites'
import { createTestRun } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type {
  Component,
  DeviceProfile,
  EnvironmentProfile,
  TestSuite
} from '@/types/models'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const readinessLoading = ref(false)
const suites = ref<TestSuite[]>([])
const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])
const selectedSuiteId = ref<number | null>(null)
const currentSuite = ref<TestSuite | null>(null)
const readinessIssues = ref<string[]>([])

const runForm = reactive({
  testSuiteId: 0,
  environmentProfileId: 0,
  deviceProfileId: null as number | null
})

const hasBlockingIssues = computed(() => readinessIssues.value.length > 0)
const hasSuiteSelected = computed(() => currentSuite.value !== null)

const primaryReadinessMessage = computed(() => readinessIssues.value[0] ?? '')

const canRunSuite = computed(() => {
  return Boolean(
    hasSuiteSelected.value &&
      !readinessLoading.value &&
      !hasBlockingIssues.value &&
      runForm.testSuiteId &&
      runForm.environmentProfileId
  )
})

function formatRunCreationError(error: unknown) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : '创建执行批次失败，请稍后重试。'
  }

  const errorMessageMap: Record<string, string> = {
    TEST_SUITE_NOT_ACTIVE: '套件未激活，无法执行。',
    PUBLISHED_VERSION_REQUIRED: '存在未发布的用例或组件，请先发布。',
    TEST_SUITE_EMPTY: '套件为空，无法执行。',
    IDEMPOTENCY_KEY_CONFLICT: '请勿重复触发相同执行请求。',
    WORKSPACE_ID_REQUIRED: '当前工作空间上下文缺失，请重新选择工作空间。',
    WORKSPACE_FORBIDDEN: '当前用户没有该工作空间权限。'
  }

  return errorMessageMap[error.code] ?? error.message
}

async function inspectSuiteReadiness(suite: TestSuite) {
  readinessLoading.value = true
  readinessIssues.value = []

  try {
    const issues: string[] = []

    if (suite.status !== 'active') {
      issues.push('当前套件状态不是 active，不能直接触发执行。')
    }

    const unpublishedCases = suite.cases.filter((item) => item.status !== 'published')
    if (unpublishedCases.length > 0) {
      issues.push('套件内存在未发布用例，请先将所有用例发布后再执行。')
    }

    if (suite.cases.length === 0) {
      issues.push('当前套件为空，至少需要一个可执行用例。')
    }

    if (suite.cases.length > 0) {
      const [caseDetails, components] = await Promise.all([
        Promise.all(suite.cases.map((item) => getTestCaseDetail(item.testCaseId))),
        listComponents()
      ])

      const componentMap = new Map<number, Component>(components.map((item) => [item.id, item]))
      const nonPublishedComponentIds = new Set<number>()

      for (const testCase of caseDetails) {
        for (const step of testCase.steps) {
          if (step.componentId === null) {
            continue
          }

          const component = componentMap.get(step.componentId)
          if (!component || component.status !== 'published') {
            nonPublishedComponentIds.add(step.componentId)
          }
        }
      }

      if (nonPublishedComponentIds.size > 0) {
        issues.push('套件引用了未发布组件，component_call 对应组件需先发布。')
      }
    }

    readinessIssues.value = issues
  } catch (error) {
    readinessIssues.value = [
      error instanceof Error ? error.message : '执行门禁检查失败，请稍后重试。'
    ]
  } finally {
    readinessLoading.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [suiteItems, environmentItems, deviceItems] = await Promise.all([
      listTestSuites(),
      listEnvironmentProfiles(),
      listDeviceProfiles()
    ])
    suites.value = suiteItems
    environmentProfiles.value = environmentItems
    deviceProfiles.value = deviceItems
    selectedSuiteId.value = suiteItems[0]?.id ?? null
    runForm.testSuiteId = suiteItems[0]?.id ?? 0
    runForm.environmentProfileId = environmentItems[0]?.id ?? 0
    runForm.deviceProfileId = deviceItems[0]?.id ?? null
  } finally {
    loading.value = false
  }
})

watch(
  selectedSuiteId,
  async (suiteId) => {
    if (!suiteId) {
      currentSuite.value = null
      runForm.testSuiteId = 0
      readinessIssues.value = []
      return
    }

    loading.value = true
    try {
      currentSuite.value = await getTestSuiteDetail(suiteId)
      runForm.testSuiteId = suiteId
      await inspectSuiteReadiness(currentSuite.value)
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

async function handleRun() {
  if (!runForm.testSuiteId || !runForm.environmentProfileId) {
    ElMessage.warning('请先补齐套件与环境信息。')
    return
  }

  if (!canRunSuite.value) {
    ElMessage.warning(primaryReadinessMessage.value || '当前套件尚未满足执行条件。')
    return
  }

  submitting.value = true
  try {
    const run = await createTestRun(runForm)
    ElMessage.success(`执行批次 ${run.id} 已创建。`)
    await router.push(`/runs/${run.id}`)
  } catch (error) {
    ElMessage.error(formatRunCreationError(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
    <SectionCard
      description="套件管理对齐 `test-suites` 与 `/cases` 子资源，保障用例顺序稳定。"
      title="套件列表"
    >
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
        description="套件详情通过 `/test-suites/{id}` 与 `/cases` 子资源实时聚合。"
        title="套件详情"
      >
        <template #action>
          <StatusTag
            v-if="currentSuite"
            :status="currentSuite.status"
          />
        </template>

        <div
          v-if="currentSuite"
          class="space-y-6"
        >
          <div class="grid grid-cols-3 gap-4">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                套件编码
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentSuite.code }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                用例数
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ currentSuite.cases.length }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">
                最近更新时间
              </p>
              <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                {{ formatDateTime(currentSuite.updatedAt) }}
              </p>
            </div>
          </div>

          <el-table
            v-loading="loading"
            :data="currentSuite.cases"
            stripe
          >
            <el-table-column
              label="顺序"
              prop="orderNo"
              width="90"
            />
            <el-table-column
              label="用例名称"
              min-width="260"
              prop="name"
            />
            <el-table-column
              label="测试用例 ID"
              prop="testCaseId"
              width="140"
            />
            <el-table-column
              label="状态"
              width="120"
            >
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
        description="创建执行批次时遵循后端真实 `POST /api/v1/test-runs` 请求体。设备预设为可选项。"
        title="触发执行"
      >
        <div
          v-if="!hasSuiteSelected"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
        >
          当前工作空间暂无可执行套件，请先完成套件编排后再触发执行。
        </div>

        <div
          v-else-if="readinessLoading"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
        >
          正在校验当前套件是否满足执行门禁...
        </div>

        <div
          v-else-if="readinessIssues.length > 0"
          class="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4"
        >
          <p class="m-0 text-sm font-medium text-amber-900">
            当前套件存在执行门禁风险
          </p>
          <ul class="mb-0 mt-3 list-disc space-y-2 pl-5 text-sm text-amber-800">
            <li
              v-for="issue in readinessIssues"
              :key="issue"
            >
              {{ issue }}
            </li>
          </ul>
        </div>

        <div
          v-else
          class="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          当前套件满足执行门禁，可以创建执行批次。
        </div>

        <div class="grid grid-cols-3 gap-4">
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
  </div>
</template>
