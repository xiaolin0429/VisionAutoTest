<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listComponents } from '@/api/modules/components'
import {
  createTestCase,
  getTestCaseDetail,
  listTestCases,
  replaceTestCaseSteps,
  updateTestCase
} from '@/api/modules/testCases'
import { listTemplates } from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import type { Component, StepWritePayload, Template, TestCase } from '@/types/models'

interface StepDraft {
  id: number
  stepNo: number
  name: string
  type: string
  templateId: number | null
  componentId: number | null
  payloadText: string
  timeoutMs: number
  retryTimes: number
}

const loading = ref(false)
const savingCase = ref(false)
const savingSteps = ref(false)

const testCases = ref<TestCase[]>([])
const components = ref<Component[]>([])
const templates = ref<Template[]>([])
const selectedCaseId = ref<number | null>(null)
const currentCase = ref<TestCase | null>(null)

const caseDialogVisible = ref(false)
const stepDialogVisible = ref(false)
const caseDialogMode = ref<'create' | 'edit'>('create')

const caseForm = reactive({
  code: '',
  name: '',
  status: 'draft',
  priority: 'p2',
  description: ''
})

const stepDrafts = ref<StepDraft[]>([])

const stepTypeOptions = [
  { label: '等待', value: 'wait' },
  { label: '点击', value: 'click' },
  { label: '输入', value: 'input' },
  { label: '模板断言', value: 'template_assert' },
  { label: 'OCR 断言', value: 'ocr_assert' },
  { label: '组件调用', value: 'component_call' }
]

const caseStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' }
]

const priorityOptions = [
  { label: 'P0', value: 'p0' },
  { label: 'P1', value: 'p1' },
  { label: 'P2', value: 'p2' },
  { label: 'P3', value: 'p3' }
]

const metrics = computed(() => [
  {
    label: '用例总数',
    value: testCases.value.length,
    hint: '映射 `test-cases` 集合资源。'
  },
  {
    label: '已发布',
    value: testCases.value.filter((item) => item.status === 'published').length,
    hint: '仅已发布用例可进入套件执行链路。'
  },
  {
    label: '当前步骤数',
    value: currentCase.value?.steps.length ?? 0,
    hint: '步骤顺序在保存时会自动重排为连续编号。'
  }
])

function stringifyPayload(payload: Record<string, unknown>) {
  return JSON.stringify(payload, null, 2)
}

function createEmptyStepDraft(index: number): StepDraft {
  return {
    id: -Date.now() - index,
    stepNo: index + 1,
    name: '',
    type: 'wait',
    templateId: null,
    componentId: null,
    payloadText: '{}',
    timeoutMs: 15000,
    retryTimes: 0
  }
}

function normalizeStepDrafts(items: StepDraft[]) {
  stepDrafts.value = items.map((item, index) => ({
    ...item,
    stepNo: index + 1
  }))
}

async function loadCaseList() {
  testCases.value = await listTestCases()

  if (!testCases.value.some((item) => item.id === selectedCaseId.value)) {
    selectedCaseId.value = testCases.value[0]?.id ?? null
  }
}

async function loadCaseDetail(testCaseId: number | null) {
  if (!testCaseId) {
    currentCase.value = null
    return
  }

  loading.value = true

  try {
    currentCase.value = await getTestCaseDetail(testCaseId)
  } finally {
    loading.value = false
  }
}

function resetCaseForm() {
  caseForm.code = ''
  caseForm.name = ''
  caseForm.status = 'draft'
  caseForm.priority = 'p2'
  caseForm.description = ''
}

function openCreateCaseDialog() {
  caseDialogMode.value = 'create'
  resetCaseForm()
  caseDialogVisible.value = true
}

function openEditCaseDialog() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  caseDialogMode.value = 'edit'
  caseForm.code = currentCase.value.code
  caseForm.name = currentCase.value.name
  caseForm.status = currentCase.value.status
  caseForm.priority = currentCase.value.priority
  caseForm.description = currentCase.value.description
  caseDialogVisible.value = true
}

async function handleSaveCase() {
  if (!caseForm.name.trim() || (caseDialogMode.value === 'create' && !caseForm.code.trim())) {
    ElMessage.warning('请补齐用例编码与名称。')
    return
  }

  savingCase.value = true

  try {
    if (caseDialogMode.value === 'create') {
      const created = await createTestCase({
        code: caseForm.code.trim(),
        name: caseForm.name.trim(),
        status: caseForm.status,
        priority: caseForm.priority,
        description: caseForm.description.trim()
      })
      selectedCaseId.value = created.id
      ElMessage.success('用例已创建。')
    } else if (currentCase.value) {
      await updateTestCase(currentCase.value.id, {
        name: caseForm.name.trim(),
        status: caseForm.status,
        priority: caseForm.priority,
        description: caseForm.description.trim()
      })
      ElMessage.success('用例已更新。')
    }

    caseDialogVisible.value = false
    await loadCaseList()
    await loadCaseDetail(selectedCaseId.value)
  } finally {
    savingCase.value = false
  }
}

async function publishCurrentCase() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  await updateTestCase(currentCase.value.id, { status: 'published' })
  ElMessage.success('用例已发布。')
  await loadCaseList()
  await loadCaseDetail(currentCase.value.id)
}

function openStepDialog() {
  if (!currentCase.value) {
    ElMessage.warning('请先选择一个用例。')
    return
  }

  normalizeStepDrafts(
    currentCase.value.steps.map((step) => ({
      id: step.id,
      stepNo: step.stepNo,
      name: step.name,
      type: step.type,
      templateId: step.templateId,
      componentId: step.componentId,
      payloadText: stringifyPayload(step.payloadJson),
      timeoutMs: step.timeoutMs,
      retryTimes: step.retryTimes
    }))
  )

  if (stepDrafts.value.length === 0) {
    normalizeStepDrafts([createEmptyStepDraft(0)])
  }

  stepDialogVisible.value = true
}

function addStepDraft() {
  normalizeStepDrafts([...stepDrafts.value, createEmptyStepDraft(stepDrafts.value.length)])
}

function removeStepDraft(index: number) {
  normalizeStepDrafts(stepDrafts.value.filter((_, currentIndex) => currentIndex !== index))
  if (stepDrafts.value.length === 0) {
    normalizeStepDrafts([createEmptyStepDraft(0)])
  }
}

function moveStep(index: number, direction: -1 | 1) {
  const nextIndex = index + direction
  if (nextIndex < 0 || nextIndex >= stepDrafts.value.length) {
    return
  }

  const nextDrafts = [...stepDrafts.value]
  const [currentItem] = nextDrafts.splice(index, 1)
  nextDrafts.splice(nextIndex, 0, currentItem)
  normalizeStepDrafts(nextDrafts)
}

function updateStepType(step: StepDraft) {
  if (step.type === 'component_call') {
    step.templateId = null
  }

  if (step.type === 'wait' || step.type === 'click' || step.type === 'input') {
    step.templateId = null
    step.componentId = null
  }
}

function parseStepPayload(step: StepDraft): Record<string, unknown> {
  try {
    const parsed = JSON.parse(step.payloadText || '{}') as unknown
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    throw new Error(`步骤 ${step.stepNo} 的 payload 不是合法 JSON。`)
  }

  throw new Error(`步骤 ${step.stepNo} 的 payload 需要是 JSON 对象。`)
}

async function handleSaveSteps() {
  if (!currentCase.value) {
    return
  }

  try {
    const payload: StepWritePayload[] = stepDrafts.value.map((step, index) => ({
      stepNo: index + 1,
      type: step.type,
      name: step.name.trim() || `Step ${index + 1}`,
      templateId: step.templateId,
      componentId: step.componentId,
      payloadJson: parseStepPayload(step),
      timeoutMs: Number(step.timeoutMs),
      retryTimes: Number(step.retryTimes)
    }))

    savingSteps.value = true
    await replaceTestCaseSteps(currentCase.value.id, payload)
    stepDialogVisible.value = false
    ElMessage.success('步骤编排已保存。')
    await loadCaseDetail(currentCase.value.id)
  } catch (error) {
    const message = error instanceof Error ? error.message : '步骤保存失败，请稍后重试。'
    ElMessage.error(message)
  } finally {
    savingSteps.value = false
  }
}

watch(
  selectedCaseId,
  async (testCaseId) => {
    await loadCaseDetail(testCaseId)
  },
  { immediate: true }
)

onMounted(async () => {
  loading.value = true

  try {
    const [caseItems, componentItems, templateItems] = await Promise.all([
      listTestCases(),
      listComponents(),
      listTemplates()
    ])

    testCases.value = caseItems
    components.value = componentItems
    templates.value = templateItems
    selectedCaseId.value = caseItems[0]?.id ?? null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
      <SectionCard
        description="对齐 `test-cases` 真实资源，支持新建、编辑与发布。"
        title="用例列表"
      >
        <template #action>
          <el-button
            color="#2563eb"
            @click="openCreateCaseDialog"
          >
            新建用例
          </el-button>
        </template>

        <el-empty
          v-if="testCases.length === 0 && !loading"
          description="当前工作空间暂无用例"
        />

        <div
          v-else
          class="space-y-3"
        >
          <button
            v-for="item in testCases"
            :key="item.id"
            :class="[
              'w-full rounded-2xl border p-4 text-left transition',
              selectedCaseId === item.id
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-200 bg-slate-50 hover:border-slate-300'
            ]"
            type="button"
            @click="selectedCaseId = item.id"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="m-0 text-base font-semibold text-slate-900">
                  {{ item.name }}
                </p>
                <p class="mb-0 mt-2 text-sm text-slate-500">
                  {{ item.code }} · {{ item.priority.toUpperCase() }}
                </p>
              </div>
              <StatusTag :status="item.status" />
            </div>
            <p class="mb-0 mt-3 text-xs text-slate-400">
              {{ formatDateTime(item.updatedAt) }}
            </p>
          </button>
        </div>
      </SectionCard>

      <div class="space-y-6">
        <SectionCard
          description="基础信息与发布状态都通过真实后端接口持久化。"
          title="用例详情"
        >
          <template #action>
            <div
              v-if="currentCase"
              class="flex gap-2"
            >
              <el-button plain @click="openEditCaseDialog">
                编辑信息
              </el-button>
              <el-button
                :disabled="currentCase.status === 'published'"
                color="#2563eb"
                @click="publishCurrentCase"
              >
                发布用例
              </el-button>
            </div>
          </template>

          <div
            v-if="currentCase"
            class="space-y-6"
          >
            <div class="grid grid-cols-4 gap-4">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">用例编码</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">{{ currentCase.code }}</p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">优先级</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                  {{ currentCase.priority.toUpperCase() }}
                </p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">公共组件数</p>
                <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
                  {{ currentCase.componentCount }}
                </p>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="m-0 text-sm text-slate-500">状态</p>
                <div class="mt-3">
                  <StatusTag :status="currentCase.status" />
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p class="m-0 text-sm text-slate-500">用例说明</p>
              <p class="mb-0 mt-3 text-sm leading-6 text-slate-700">
                {{ currentCase.description || '暂无说明' }}
              </p>
            </div>
          </div>

          <el-empty
            v-else
            description="暂无用例数据"
          />
        </SectionCard>

        <SectionCard
          description="步骤顺序从 1 开始连续，支持新增、调整、保存与引用模板/组件。"
          title="步骤编排"
        >
          <template #action>
            <el-button
              :disabled="!currentCase"
              color="#2563eb"
              @click="openStepDialog"
            >
              编排步骤
            </el-button>
          </template>

          <el-table
            v-loading="loading"
            :data="currentCase?.steps ?? []"
            empty-text="当前用例暂无步骤"
            stripe
          >
            <el-table-column label="Step No" prop="stepNo" width="90" />
            <el-table-column label="步骤名称" min-width="220" prop="name" />
            <el-table-column label="类型" min-width="150" prop="type" />
            <el-table-column label="目标" min-width="220" prop="target" />
            <el-table-column label="备注" min-width="280" prop="note" />
          </el-table>
        </SectionCard>
      </div>
    </div>

    <el-dialog
      v-model="caseDialogVisible"
      :title="caseDialogMode === 'create' ? '新建测试用例' : '编辑测试用例'"
      width="560px"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">用例编码</label>
          <el-input
            v-model="caseForm.code"
            :disabled="caseDialogMode === 'edit'"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">优先级</label>
          <el-select
            v-model="caseForm.priority"
            class="!w-full"
          >
            <el-option
              v-for="option in priorityOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">用例名称</label>
          <el-input v-model="caseForm.name" />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">状态</label>
          <el-select
            v-model="caseForm.status"
            class="!w-full"
          >
            <el-option
              v-for="option in caseStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
          <el-input
            v-model="caseForm.description"
            :rows="4"
            type="textarea"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="caseDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingCase"
            color="#2563eb"
            @click="handleSaveCase"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="stepDialogVisible"
      title="步骤编排"
      top="4vh"
      width="960px"
    >
      <div class="mb-4 flex justify-between">
        <p class="m-0 text-sm text-slate-500">
          支持编辑步骤名称、类型、模板/组件引用以及 `payload_json`。
        </p>
        <el-button plain @click="addStepDraft">
          新增步骤
        </el-button>
      </div>

      <div class="max-h-[65vh] space-y-4 overflow-auto pr-2">
        <div
          v-for="(step, index) in stepDrafts"
          :key="step.id"
          class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
        >
          <div class="mb-4 flex items-center justify-between">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                Step {{ step.stepNo }}
              </p>
              <p class="mb-0 mt-1 text-xs text-slate-400">
                顺序会在保存时自动归一化。
              </p>
            </div>
            <div class="flex gap-2">
              <el-button plain @click="moveStep(index, -1)">
                上移
              </el-button>
              <el-button plain @click="moveStep(index, 1)">
                下移
              </el-button>
              <el-button
                link
                type="danger"
                @click="removeStepDraft(index)"
              >
                删除
              </el-button>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">步骤名称</label>
              <el-input v-model="step.name" />
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">步骤类型</label>
              <el-select
                v-model="step.type"
                class="!w-full"
                @change="updateStepType(step)"
              >
                <el-option
                  v-for="option in stepTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">模板引用</label>
              <el-select
                v-model="step.templateId"
                class="!w-full"
                clearable
                placeholder="可选"
              >
                <el-option
                  v-for="item in templates"
                  :key="item.id"
                  :label="`${item.name} (#${item.id})`"
                  :value="item.id"
                />
              </el-select>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">组件引用</label>
              <el-select
                v-model="step.componentId"
                class="!w-full"
                clearable
                placeholder="可选"
              >
                <el-option
                  v-for="item in components"
                  :key="item.id"
                  :label="`${item.name} (#${item.id})`"
                  :value="item.id"
                />
              </el-select>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">超时时间(ms)</label>
              <el-input-number
                v-model="step.timeoutMs"
                :min="1"
                class="!w-full"
              />
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">重试次数</label>
              <el-input-number
                v-model="step.retryTimes"
                :min="0"
                class="!w-full"
              />
            </div>
            <div class="col-span-2">
              <label class="mb-2 block text-sm font-medium text-slate-700">payload_json</label>
              <el-input
                v-model="step.payloadText"
                :rows="5"
                type="textarea"
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="stepDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingSteps"
            color="#2563eb"
            @click="handleSaveSteps"
          >
            保存步骤
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
