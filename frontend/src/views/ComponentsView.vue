<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  createComponent,
  getComponentDetail,
  getComponentSteps,
  listComponents,
  replaceComponentSteps,
  updateComponent
} from '@/api/modules/components'
import { listTemplates } from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import {
  LONG_PRESS_BUTTON_OPTIONS,
  NAVIGATE_WAIT_UNTIL_OPTIONS,
  OCR_MATCH_MODE_OPTIONS,
  SCROLL_BEHAVIOR_OPTIONS,
  SCROLL_DIRECTION_OPTIONS,
  SCROLL_TARGET_OPTIONS,
  STEP_TYPE_LABELS,
  buildStepDraft,
  buildStepWritePayload,
  createEmptyStepDraft,
  createStepTypeOptions,
  normalizeStepByType,
  normalizeStepDrafts as normalizeStepDraftItems,
  validateStepDraft,
  type StepDraft,
  type StepValidationErrors
} from '@/utils/steps'
import type { Component, StepType, Template } from '@/types/models'

const loading = ref(false)
const savingComponent = ref(false)
const savingSteps = ref(false)
const stepSubmitAttempted = ref(false)

const components = ref<Component[]>([])
const templates = ref<Template[]>([])
const selectedComponentId = ref<number | null>(null)
const currentComponent = ref<Component | null>(null)

const componentDialogVisible = ref(false)
const stepDialogVisible = ref(false)
const componentDialogMode = ref<'create' | 'edit'>('create')

const componentForm = reactive({
  code: '',
  name: '',
  status: 'draft',
  description: ''
})

const stepDrafts = ref<StepDraft[]>([])
const stepTypeOptions = createStepTypeOptions({ allowComponentCall: false })

const componentStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' }
]

const metrics = computed(() => [
  {
    label: '组件总数',
    value: components.value.length,
    hint: '映射 `components` 集合资源。'
  },
  {
    label: '已发布',
    value: components.value.filter((item) => item.status === 'published').length,
    hint: '仅已发布组件可被用例引用。'
  },
  {
    label: '当前步骤数',
    value: currentComponent.value?.steps?.length ?? 0,
    hint: '步骤顺序在保存时会自动重排为连续编号。'
  }
])

const stepValidationErrors = computed(() => {
  return stepDrafts.value.map((step) => validateStepDraft(step))
})

const hasStepValidationErrors = computed(() => {
  return stepValidationErrors.value.some((item) => Object.keys(item).length > 0)
})

function normalizeStepDrafts(items: StepDraft[]) {
  stepDrafts.value = normalizeStepDraftItems(items)
}

function getStepError(index: number, field: keyof StepValidationErrors) {
  return stepValidationErrors.value[index]?.[field] ?? ''
}

function updateStepType(step: StepDraft, nextType: StepType) {
  Object.assign(step, normalizeStepByType(step, nextType))
}

function handleStepTypeModelUpdate(step: StepDraft, value: string | number | boolean) {
  updateStepType(step, value as StepType)
}

async function loadComponents() {
  loading.value = true
  try {
    components.value = await listComponents()
  } catch {
    ElMessage.error('加载组件列表失败')
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    templates.value = await listTemplates()
  } catch {
    ElMessage.error('加载模板列表失败')
  }
}

async function selectComponent(componentId: number) {
  selectedComponentId.value = componentId
  loading.value = true
  try {
    const [detail, steps] = await Promise.all([
      getComponentDetail(componentId),
      getComponentSteps(componentId)
    ])
    currentComponent.value = { ...detail, steps }
    normalizeStepDrafts(steps.map((step) => buildStepDraft(step)))
  } catch {
    ElMessage.error('加载组件详情失败')
    currentComponent.value = null
    stepDrafts.value = []
  } finally {
    loading.value = false
  }
}

function openCreateComponentDialog() {
  componentDialogMode.value = 'create'
  componentForm.code = ''
  componentForm.name = ''
  componentForm.status = 'draft'
  componentForm.description = ''
  componentDialogVisible.value = true
}

function openEditComponentDialog() {
  if (!currentComponent.value) {
    return
  }

  componentDialogMode.value = 'edit'
  componentForm.code = currentComponent.value.code
  componentForm.name = currentComponent.value.name
  componentForm.status = currentComponent.value.status
  componentForm.description = currentComponent.value.description
  componentDialogVisible.value = true
}

async function submitComponentForm() {
  savingComponent.value = true
  try {
    if (componentDialogMode.value === 'create') {
      const created = await createComponent({
        code: componentForm.code,
        name: componentForm.name,
        description: componentForm.description
      })
      await loadComponents()
      await selectComponent(created.id)
      ElMessage.success('组件创建成功')
    } else {
      if (!currentComponent.value) {
        return
      }

      await updateComponent(currentComponent.value.id, {
        name: componentForm.name,
        description: componentForm.description,
        status: componentForm.status
      })
      await loadComponents()
      await selectComponent(currentComponent.value.id)
      ElMessage.success('组件更新成功')
    }

    componentDialogVisible.value = false
  } catch {
    ElMessage.error(componentDialogMode.value === 'create' ? '创建失败' : '更新失败')
  } finally {
    savingComponent.value = false
  }
}

function openStepDialog() {
  if (!currentComponent.value) {
    ElMessage.warning('请先选择一个组件。')
    return
  }

  stepSubmitAttempted.value = false
  if (stepDrafts.value.length === 0) {
    normalizeStepDrafts([createEmptyStepDraft(0)])
  }
  stepDialogVisible.value = true
}

function addStep() {
  normalizeStepDrafts([...stepDrafts.value, createEmptyStepDraft(stepDrafts.value.length)])
}

function removeStep(index: number) {
  normalizeStepDrafts(stepDrafts.value.filter((_, currentIndex) => currentIndex !== index))
}

function moveStepUp(index: number) {
  if (index === 0) {
    return
  }

  const nextDrafts = [...stepDrafts.value]
  const [currentItem] = nextDrafts.splice(index, 1)
  nextDrafts.splice(index - 1, 0, currentItem)
  normalizeStepDrafts(nextDrafts)
}

function moveStepDown(index: number) {
  if (index === stepDrafts.value.length - 1) {
    return
  }

  const nextDrafts = [...stepDrafts.value]
  const [currentItem] = nextDrafts.splice(index, 1)
  nextDrafts.splice(index + 1, 0, currentItem)
  normalizeStepDrafts(nextDrafts)
}

async function submitSteps() {
  stepSubmitAttempted.value = true
  if (hasStepValidationErrors.value) {
    ElMessage.warning('请修正步骤配置错误')
    return
  }

  if (!currentComponent.value) {
    return
  }

  savingSteps.value = true
  try {
    const payload = stepDrafts.value.map((step, index) => buildStepWritePayload(step, index))
    await replaceComponentSteps(currentComponent.value.id, payload)
    await selectComponent(currentComponent.value.id)
    ElMessage.success('步骤保存成功')
    stepDialogVisible.value = false
  } catch (error) {
    const message =
      error instanceof ApiError && error.code === 'STEP_CONFIGURATION_INVALID'
        ? error.message
        : '步骤保存失败'
    ElMessage.error(message)
  } finally {
    savingSteps.value = false
  }
}

function getStepTemplateOptions(step: StepDraft) {
  if (step.type !== 'template_assert' && step.type !== 'ocr_assert') {
    return []
  }

  const expectedStrategy = step.type === 'template_assert' ? 'template' : 'ocr'
  return templates.value
    .filter((item) => item.matchStrategy === expectedStrategy)
    .map((item) => ({
      value: item.id,
      label: `${item.name} (#${item.id}) · ${item.status}`
    }))
}

watch(selectedComponentId, (newId) => {
  if (newId !== null) {
    void selectComponent(newId)
  }
})

onMounted(() => {
  void loadComponents()
  void loadTemplates()
})
</script>

<template>
  <div class="components-view">
    <div class="metrics-row">
      <MetricCard v-for="metric in metrics" :key="metric.label" v-bind="metric" />
    </div>

    <div class="content-layout">
      <aside class="sidebar">
        <SectionCard title="组件列表">
          <template #action>
            <el-button type="primary" size="small" @click="openCreateComponentDialog">
              新建组件
            </el-button>
          </template>
          <el-scrollbar v-loading="loading" height="calc(100vh - 280px)">
            <div class="component-list">
              <div
                v-for="component in components"
                :key="component.id"
                class="component-item"
                :class="{ active: selectedComponentId === component.id }"
                @click="selectComponent(component.id)"
              >
                <div class="component-header">
                  <span class="component-name">{{ component.name }}</span>
                  <StatusTag :status="component.status" size="small" />
                </div>
                <div class="component-meta">{{ component.code }}</div>
              </div>
              <el-empty v-if="components.length === 0" description="暂无组件" />
            </div>
          </el-scrollbar>
        </SectionCard>
      </aside>

      <main class="main-content">
        <SectionCard v-if="currentComponent" title="组件详情">
          <template #action>
            <el-button size="small" @click="openEditComponentDialog">编辑组件</el-button>
            <el-button type="primary" size="small" @click="openStepDialog">编排步骤</el-button>
          </template>
          <div class="component-detail">
            <div class="detail-row">
              <span class="label">组件编码：</span>
              <span>{{ currentComponent.code }}</span>
            </div>
            <div class="detail-row">
              <span class="label">组件名称：</span>
              <span>{{ currentComponent.name }}</span>
            </div>
            <div class="detail-row">
              <span class="label">状态：</span>
              <StatusTag :status="currentComponent.status" />
            </div>
            <div class="detail-row">
              <span class="label">描述：</span>
              <span>{{ currentComponent.description || '--' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">发布时间：</span>
              <span>{{ currentComponent.publishedAt ? formatDateTime(currentComponent.publishedAt) : '--' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">创建时间：</span>
              <span>{{ formatDateTime(currentComponent.createdAt) }}</span>
            </div>
          </div>

          <div v-if="currentComponent.steps && currentComponent.steps.length > 0" class="steps-section">
            <h4>步骤列表</h4>
            <el-table :data="currentComponent.steps" stripe>
              <el-table-column prop="stepNo" label="序号" width="80" />
              <el-table-column prop="name" label="步骤名称" min-width="150" />
              <el-table-column label="类型" width="120">
                <template #default="{ row }">{{ STEP_TYPE_LABELS[row.type as StepType] }}</template>
              </el-table-column>
              <el-table-column prop="target" label="摘要" min-width="220" />
              <el-table-column prop="note" label="配置说明" min-width="260" />
            </el-table>
          </div>
          <el-empty v-else description="暂无步骤，点击「编排步骤」开始配置" />
        </SectionCard>
        <el-empty v-else description="请从左侧选择组件" />
      </main>
    </div>

    <el-dialog
      v-model="componentDialogVisible"
      :title="componentDialogMode === 'create' ? '新建组件' : '编辑组件'"
      width="600px"
    >
      <el-form :model="componentForm" label-width="100px">
        <el-form-item label="组件编码">
          <el-input
            v-model="componentForm.code"
            :disabled="componentDialogMode === 'edit'"
            placeholder="例如：login_flow"
          />
        </el-form-item>
        <el-form-item label="组件名称">
          <el-input v-model="componentForm.name" placeholder="例如：登录流程" />
        </el-form-item>
        <el-form-item v-if="componentDialogMode === 'edit'" label="状态">
          <el-select v-model="componentForm.status">
            <el-option
              v-for="option in componentStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="componentForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="componentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingComponent" @click="submitComponentForm">
          {{ componentDialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="stepDialogVisible" title="编排步骤" width="90%" top="5vh">
      <div class="step-editor">
        <div class="step-toolbar">
          <el-button type="primary" size="small" @click="addStep">添加步骤</el-button>
          <el-button type="success" size="small" :loading="savingSteps" @click="submitSteps">
            保存步骤
          </el-button>
        </div>

        <div
          v-if="stepSubmitAttempted && hasStepValidationErrors"
          class="mb-4 rounded border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          请修正步骤配置后再保存。
        </div>

        <div v-for="(step, index) in stepDrafts" :key="step.id" class="step-card">
          <div class="step-header">
            <span class="step-number">步骤 {{ step.stepNo }}</span>
            <div class="step-actions">
              <el-button size="small" :disabled="index === 0" @click="moveStepUp(index)">上移</el-button>
              <el-button size="small" :disabled="index === stepDrafts.length - 1" @click="moveStepDown(index)">
                下移
              </el-button>
              <el-button type="danger" size="small" @click="removeStep(index)">删除</el-button>
            </div>
          </div>

          <el-form label-width="120px" class="step-form">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="步骤名称">
                  <el-input v-model="step.name" placeholder="例如：点击登录按钮" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="步骤类型">
                  <el-select
                    :model-value="step.type"
                    style="width: 100%"
                    @update:model-value="handleStepTypeModelUpdate(step, $event)"
                  >
                    <el-option
                      v-for="option in stepTypeOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'wait'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="等待时间(ms)" :error="getStepError(index, 'waitMs')">
                  <el-input-number v-model="step.waitMs" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'click' || step.type === 'input' || step.type === 'ocr_assert'" :gutter="20">
              <el-col :span="24">
                <el-form-item label="选择器" :error="getStepError(index, 'selector')">
                  <el-input v-model="step.selector" placeholder="CSS 选择器" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'navigate'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="URL / 相对路径" :error="getStepError(index, 'url')">
                  <el-input
                    v-model="step.url"
                    placeholder="/login 或 https://example.com/orders/123"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="等待策略" :error="getStepError(index, 'waitUntil')">
                  <el-select v-model="step.waitUntil" style="width: 100%">
                    <el-option
                      v-for="option in NAVIGATE_WAIT_UNTIL_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'scroll'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="滑动目标" :error="getStepError(index, 'scrollTarget')">
                  <el-select v-model="step.scrollTarget" style="width: 100%">
                    <el-option
                      v-for="option in SCROLL_TARGET_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="滑动方向" :error="getStepError(index, 'direction')">
                  <el-select v-model="step.direction" style="width: 100%">
                    <el-option
                      v-for="option in SCROLL_DIRECTION_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'scroll' && step.scrollTarget === 'element'" :gutter="20">
              <el-col :span="24">
                <el-form-item label="目标元素选择器" :error="getStepError(index, 'selector')">
                  <el-input v-model="step.selector" placeholder=".table-container" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'scroll'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="滑动距离(px)" :error="getStepError(index, 'distance')">
                  <el-input-number v-model="step.distance" :min="1" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="滑动行为" :error="getStepError(index, 'behavior')">
                  <el-select v-model="step.behavior" style="width: 100%">
                    <el-option
                      v-for="option in SCROLL_BEHAVIOR_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'long_press'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="选择器" :error="getStepError(index, 'selector')">
                  <el-input v-model="step.selector" placeholder="[data-testid='card']" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="长按时长(ms)" :error="getStepError(index, 'durationMs')">
                  <el-input-number v-model="step.durationMs" :min="1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'long_press'" :gutter="20">
              <el-col :span="24">
                <el-form-item label="按钮类型" :error="getStepError(index, 'button')">
                  <el-select v-model="step.button" style="width: 100%">
                    <el-option
                      v-for="option in LONG_PRESS_BUTTON_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'input'" :gutter="20">
              <el-col :span="24">
                <el-form-item label="输入文本" :error="getStepError(index, 'text')">
                  <el-input v-model="step.text" placeholder="支持变量占位符 {{ variable }}" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'template_assert' || step.type === 'ocr_assert'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="模板" :error="getStepError(index, 'templateId')">
                  <el-select v-model="step.templateId" clearable style="width: 100%">
                    <el-option
                      v-for="option in getStepTemplateOptions(step)"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col v-if="step.type === 'template_assert'" :span="12">
                <el-form-item label="阈值">
                  <el-input-number v-model="step.threshold" :min="0" :max="1" :step="0.01" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row v-if="step.type === 'ocr_assert'" :gutter="20">
              <el-col :span="12">
                <el-form-item label="期望文本" :error="getStepError(index, 'expectedText')">
                  <el-input v-model="step.expectedText" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="匹配模式">
                  <el-select v-model="step.matchMode" style="width: 100%">
                    <el-option
                      v-for="option in OCR_MATCH_MODE_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="区分大小写">
                  <el-switch v-model="step.caseSensitive" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="超时(ms)" :error="getStepError(index, 'timeoutMs')">
                  <el-input-number v-model="step.timeoutMs" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="重试次数" :error="getStepError(index, 'retryTimes')">
                  <el-input-number v-model="step.retryTimes" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="额外 Payload" :error="getStepError(index, 'extraPayloadJson')">
                  <el-input v-model="step.extraPayloadJson" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <el-empty v-if="stepDrafts.length === 0" description="暂无步骤，点击「添加步骤」开始配置" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.components-view {
  padding: 20px;
}

.metrics-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.content-layout {
  display: flex;
  gap: 20px;
}

.sidebar {
  width: 320px;
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  min-width: 0;
}

.component-list {
  padding: 8px;
}

.component-item {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e4e7ed;
}

.component-item:hover {
  background-color: #f5f7fa;
}

.component-item.active {
  background-color: #ecf5ff;
  border-color: #409eff;
}

.component-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.component-name {
  font-weight: 500;
  font-size: 14px;
}

.component-meta {
  font-size: 12px;
  color: #909399;
}

.component-detail {
  margin-bottom: 24px;
}

.detail-row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.detail-row .label {
  width: 120px;
  color: #606266;
  font-weight: 500;
}

.steps-section {
  margin-top: 24px;
}

.steps-section h4 {
  margin-bottom: 12px;
  font-size: 16px;
  color: #303133;
}

.step-editor {
  max-height: 70vh;
  overflow-y: auto;
}

.step-toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
}

.step-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 16px;
  background-color: #fafafa;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.step-number {
  font-weight: 600;
  font-size: 14px;
  color: #409eff;
}

.step-actions {
  display: flex;
  gap: 8px;
}

.step-form {
  background-color: white;
  padding: 16px;
  border-radius: 4px;
}
</style>


