<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { getTestSuiteDetail, listTestSuites } from '@/api/modules/testSuites'
import { createTestRun } from '@/api/modules/testRuns'
import { formatDateTime } from '@/utils/format'
import type { DeviceProfile, EnvironmentProfile, TestSuite } from '@/types/models'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const suites = ref<TestSuite[]>([])
const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])
const selectedSuiteId = ref<number | null>(null)
const currentSuite = ref<TestSuite | null>(null)

const runForm = reactive({
  testSuiteId: 0,
  environmentProfileId: 0,
  deviceProfileId: null as number | null
})

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
      return
    }

    loading.value = true
    try {
      currentSuite.value = await getTestSuiteDetail(suiteId)
      runForm.testSuiteId = suiteId
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

  submitting.value = true
  try {
    const run = await createTestRun(runForm)
    ElMessage.success(`执行批次 ${run.id} 已创建。`)
    await router.push(`/runs/${run.id}`)
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
      <div class="space-y-3">
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
