<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import { listComponents } from '@/api/modules/components'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { getTestCaseDetail, listTestCases } from '@/api/modules/testCases'
import {
  createTestSuite,
  getTestSuiteDetail,
  listTestSuites,
  replaceSuiteCases,
  updateTestSuite
} from '@/api/modules/testSuites'
import { createTestRun } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type {
  Component,
  DeviceProfile,
  EnvironmentProfile,
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
const readinessLoading = ref(false)

const suites = ref<TestSuite[]>([])
const testCases = ref<TestCase[]>([])
const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])

const selectedSuiteId = ref<number | null>(null)
const currentSuite = ref<TestSuite | null>(null)
const readinessIssues = ref<string[]>([])

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

const hasBlockingIssues = computed(() => readinessIssues.value.length > 0)
const hasSuiteSelected = computed(() => currentSuite.value !== null)
const primaryReadinessMessage = computed(() => readinessIssues.value[0] ?? '')

const availableCasesToAdd = computed(() => {
  const selectedIds = new Set(suiteCaseDrafts.value.map((item) => item.testCaseId))
  return testCases.value.filter((item) => !selectedIds.has(item.id))
})

const canRunSuite = computed(() => {
  return Boolean(
    hasSuiteSelected.value &&
      !readinessLoading.value &&
      !hasBlockingIssues.value &&
      runForm.testSuiteId &&
      runForm.environmentProfileId
  )
})

function normalizeSuiteCases(items: SuiteCaseDraft[]) {
  suiteCaseDrafts.value = items.map((item, index) => ({
    ...item,
    orderNo: index + 1
  }))
}

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

async function loadPageData() {
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
  if (!suiteId) {
    currentSuite.value = null
    readinessIssues.value = []
    runForm.testSuiteId = 0
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
}

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
  <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
    <SectionCard
      description="套件管理对齐 `test-suites` 与 `/cases` 子资源，支持新建、编辑和编排。"
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
        description="套件详情通过 `/test-suites/{id}` 与 `/cases` 子资源实时聚合。"
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
          <div class="grid grid-cols-4 gap-4">
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

    <el-dialog
      v-model="suiteDialogVisible"
      :title="suiteDialogMode === 'create' ? '新建测试套件' : '编辑测试套件'"
      width="560px"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">套件编码</label>
          <el-input
            v-model="suiteForm.code"
            :disabled="suiteDialogMode === 'edit'"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">状态</label>
          <el-select
            v-model="suiteForm.status"
            class="!w-full"
          >
            <el-option
              v-for="option in suiteStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">套件名称</label>
          <el-input v-model="suiteForm.name" />
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
          <el-input
            v-model="suiteForm.description"
            :rows="4"
            type="textarea"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="suiteDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingSuite"
            color="#2563eb"
            @click="handleSaveSuite"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="caseDialogVisible"
      title="编排套件用例"
      width="780px"
    >
      <div class="mb-4 grid grid-cols-[minmax(0,1fr)_auto] gap-3">
        <el-select
          v-model="selectedCaseToAdd"
          class="!w-full"
          filterable
          clearable
          placeholder="选择一个测试用例加入套件"
        >
          <el-option
            v-for="item in availableCasesToAdd"
            :key="item.id"
            :label="`${item.name} (${item.code})`"
            :value="item.id"
          />
        </el-select>
        <el-button plain @click="addSuiteCase">
          加入套件
        </el-button>
      </div>

      <div class="space-y-3">
        <div
          v-for="(item, index) in suiteCaseDrafts"
          :key="item.testCaseId"
          class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 p-4"
        >
          <div>
            <p class="m-0 text-base font-semibold text-slate-900">
              {{ item.orderNo }}. {{ item.name }}
            </p>
            <p class="mb-0 mt-2 text-sm text-slate-500">
              测试用例 #{{ item.testCaseId }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <StatusTag :status="item.status" />
            <el-button plain @click="moveSuiteCase(index, -1)">
              上移
            </el-button>
            <el-button plain @click="moveSuiteCase(index, 1)">
              下移
            </el-button>
            <el-button
              link
              type="danger"
              @click="removeSuiteCase(index)"
            >
              移除
            </el-button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="caseDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingCases"
            color="#2563eb"
            @click="handleSaveSuiteCases"
          >
            保存编排
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
