<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import StepEditorDialog from '@/components/step/StepEditorDialog.vue'
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
import { STEP_TYPE_LABELS, type StepDraft } from '@/utils/steps'
import { useStepEditor } from '@/composables/useStepEditor'
import type { Component, StepType, Template } from '@/types/models'

const loading = ref(false)
const savingComponent = ref(false)

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

const stepEditor = useStepEditor({ allowComponentCall: false })

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
  } catch {
    ElMessage.error('加载组件详情失败')
    currentComponent.value = null
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
  stepEditor.initFromSteps(currentComponent.value.steps ?? [])
  stepDialogVisible.value = true
}

async function submitSteps() {
  if (!currentComponent.value) return
  const success = await stepEditor.saveSteps(async (payload) => {
    await replaceComponentSteps(currentComponent.value!.id, payload)
  })
  if (success) {
    stepDialogVisible.value = false
    await selectComponent(currentComponent.value.id)
  }
}

function getStepTemplateOptions(step: StepDraft) {
  if (step.type !== 'template_assert' && step.type !== 'ocr_assert') return []
  const expectedStrategy = step.type === 'template_assert' ? 'template' : 'ocr'
  return templates.value
    .filter((item) => item.matchStrategy === expectedStrategy)
    .map((item) => ({ id: item.id, label: `${item.name} (#${item.id}) · ${item.status}` }))
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

    <StepEditorDialog
      :visible="stepDialogVisible"
      title="编排步骤"
      :step-drafts="stepEditor.stepDrafts.value"
      :saving-steps="stepEditor.savingSteps.value"
      :step-submit-attempted="stepEditor.stepSubmitAttempted.value"
      :has-step-validation-errors="stepEditor.hasStepValidationErrors.value"
      :step-type-options="stepEditor.stepTypeOptions"
      :templates="templates"
      :allow-component-call="false"
      :get-step-error-fn="stepEditor.getStepError"
      :should-open-advanced-payload-fn="stepEditor.shouldOpenAdvancedPayload"
      :get-step-template-options-fn="getStepTemplateOptions"
      @update:visible="stepDialogVisible = $event"
      @add-step="stepEditor.addStep()"
      @remove-step="stepEditor.removeStep($event)"
      @move-step="(index, direction) => stepEditor.moveStep(index, direction)"
      @update-step-type="(step, value) => stepEditor.handleStepTypeModelUpdate(step, value)"
      @save="submitSteps"
      @closed="stepEditor.resetState()"
    />
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
</style>
