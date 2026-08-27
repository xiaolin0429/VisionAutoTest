<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  CopyDocument,
  Delete,
  DocumentCopy,
  Scissor
} from '@element-plus/icons-vue'

import ConditionalBranchFields from '@/components/step/ConditionalBranchFields.vue'
import ConditionalBranchMetadataFields from '@/components/step/ConditionalBranchMetadataFields.vue'
import StepAdvancedPayloadField from '@/components/step/StepAdvancedPayloadField.vue'
import StepRuntimeFields from '@/components/step/StepRuntimeFields.vue'
import StepTypeFields from '@/components/step/StepTypeFields.vue'
import type { StepCanvasInspectorTab } from './StepCanvasInspectorPanel.vue'
import type { Component, StepType, Template } from '@/types/models'
import type {
  EditableStepPath,
  StepGraphAnnotation,
  StepGraphAnnotationKind,
  StepGraphNode,
  StepGraphNodeDisplayState,
  StepStructurePath
} from '@/types/stepGraph'
import {
  createStepTypeOptions,
  validateStepDraft,
  type ConditionalBranchDraft,
  type StepDraft,
  type StepFieldErrorGetter,
  type StepTemplateOption,
  type StepTypeOption,
  type StepValidationErrors
} from '@/utils/steps'

export type StepCanvasInspectorCommand =
  | 'copy'
  | 'cut'
  | 'paste'
  | 'duplicate'
  | 'delete'

const props = withDefaults(
  defineProps<{
    activeTab: StepCanvasInspectorTab
    selectedNode?: StepGraphNode | null
    selectedStep?: StepDraft | null
    selectedBranch?: ConditionalBranchDraft | null
    selectedElseStep?: StepDraft | null
    selectedPaths?: StepStructurePath[]
    editableNodes?: StepGraphNode[]
    displayNodeState?: StepGraphNodeDisplayState
    annotations?: StepGraphAnnotation[]
    templates?: Template[]
    components?: Component[]
    allowComponentCall?: boolean
    validateStepFn?: (step: StepDraft) => StepValidationErrors
    getStepTemplateOptionsFn: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
    formatComponentOptionLabelFn?: (component: Component) => string
  }>(),
  {
    selectedNode: null,
    selectedStep: null,
    selectedBranch: null,
    selectedElseStep: null,
    selectedPaths: () => [],
    editableNodes: () => [],
    displayNodeState: () => ({}),
    annotations: () => [],
    templates: () => [],
    components: () => [],
    allowComponentCall: true,
    validateStepFn: validateStepDraft,
    getStepTemplateHintFn: undefined,
    formatComponentOptionLabelFn: undefined
  }
)

const emit = defineEmits<{
  (event: 'update-step-type', value: StepType): void
  (event: 'update-child-step-type', step: StepDraft, value: StepType): void
  (event: 'update-branch-key', value: string): void
  (event: 'command', command: StepCanvasInspectorCommand): void
  (event: 'apply-style', patch: StepGraphNodeDisplayState): void
  (event: 'reset-style'): void
  (
    event: 'create-annotation',
    value: {
      target: EditableStepPath
      kind: StepGraphAnnotationKind
      label: string
    }
  ): void
  (event: 'delete-annotation', id: string): void
}>()

const relationTarget = ref<EditableStepPath | null>(null)
const relationKind = ref<StepGraphAnnotationKind>('dependency')
const relationLabel = ref('')
const commandToolbarRef = ref<HTMLElement | null>(null)

const selectedCount = computed((): number => props.selectedPaths.length)
const selectedEditablePath = computed((): EditableStepPath | null => {
  const path = props.selectedNode?.path
  return path && props.selectedNode?.editable ? path as EditableStepPath : null
})
const relatedAnnotations = computed(
  (): StepGraphAnnotation[] =>
    selectedEditablePath.value
      ? props.annotations.filter(
          (annotation: StepGraphAnnotation): boolean =>
            annotation.source === selectedEditablePath.value ||
            annotation.target === selectedEditablePath.value
        )
      : []
)
const relationTargets = computed(
  (): StepGraphNode[] =>
    props.editableNodes.filter(
      (node: StepGraphNode): boolean => node.path !== selectedEditablePath.value
    )
)
const stepTypeOptions = computed(() => {
  const options = createStepTypeOptions({
    allowComponentCall: props.allowComponentCall
  })
  if (props.selectedNode?.kind !== 'branch-step') {
    return options
  }
  return options.filter(
    (option: StepTypeOption): boolean =>
      option.value !== 'component_call' && option.value !== 'conditional_branch'
  )
})
const validationErrors = computed(
  (): StepValidationErrors =>
    props.selectedStep ? props.validateStepFn(props.selectedStep) : {}
)
const getFieldError: StepFieldErrorGetter = (
  field: keyof StepValidationErrors
): string => validationErrors.value[field] ?? ''
const branchTemplateOptions = computed(
  (): StepTemplateOption[] =>
    props.templates
      .filter((template: Template): boolean => template.matchStrategy === 'template')
      .map((template: Template): StepTemplateOption => ({
        id: template.id,
        label: `${template.name} (#${template.id})`
      }))
)
const colorPalette = [
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#4f46e5',
  '#0891b2',
  '#64748b',
  '#e11d48'
]

function submitAnnotation(): void {
  if (!relationTarget.value) {
    return
  }
  emit('create-annotation', {
    target: relationTarget.value,
    kind: relationKind.value,
    label: relationLabel.value
  })
  relationLabel.value = ''
}

function updateBranchChildType(
  step: StepDraft,
  value: string | number | boolean
): void {
  emit('update-child-step-type', step, value as StepType)
}

function moveCommandFocus(event: KeyboardEvent, direction: -1 | 1): void {
  const toolbar = commandToolbarRef.value
  const target = event.target
  if (!toolbar || !(target instanceof Element)) {
    return
  }
  const buttons = Array.from(
    toolbar.querySelectorAll<HTMLButtonElement>('button:not([disabled])')
  ).filter(
    (button: HTMLButtonElement): boolean =>
      button.getAttribute('aria-disabled') !== 'true' && button.tabIndex >= 0
  )
  if (buttons.length === 0) {
    return
  }
  const currentButton = target.closest<HTMLButtonElement>('button')
  const currentIndex = currentButton ? buttons.indexOf(currentButton) : -1
  const nextIndex =
    currentIndex < 0
      ? 0
      : (currentIndex + direction + buttons.length) % buttons.length
  event.preventDefault()
  event.stopPropagation()
  buttons[nextIndex].focus()
}

watch(
  selectedEditablePath,
  (): void => {
    relationTarget.value = null
    relationLabel.value = ''
  }
)
</script>

<template>
  <div v-if="!selectedNode" class="inspector-empty">
    在画布或大纲中选择节点以查看配置。
  </div>

  <template v-else-if="activeTab === 'config'">
    <div v-if="selectedStep" class="space-y-4">
      <div
        ref="commandToolbarRef"
        aria-label="所选步骤命令"
        class="inspector-command-row"
        role="toolbar"
        @keydown.left="moveCommandFocus($event, -1)"
        @keydown.right="moveCommandFocus($event, 1)"
      >
        <el-tooltip content="复制 Cmd/Ctrl+C" placement="top">
          <el-button :icon="CopyDocument" aria-label="复制所选步骤" @click="emit('command', 'copy')" />
        </el-tooltip>
        <el-tooltip content="剪切 Cmd/Ctrl+X" placement="top">
          <el-button :icon="Scissor" aria-label="剪切所选步骤" @click="emit('command', 'cut')" />
        </el-tooltip>
        <el-tooltip content="粘贴 Cmd/Ctrl+V" placement="top">
          <el-button :icon="DocumentCopy" aria-label="粘贴步骤" @click="emit('command', 'paste')" />
        </el-tooltip>
        <el-tooltip content="重复 Cmd/Ctrl+D" placement="top">
          <el-button :icon="CopyDocument" aria-label="重复所选步骤" @click="emit('command', 'duplicate')" />
        </el-tooltip>
        <el-tooltip content="删除 Delete/Backspace" placement="top">
          <el-button
            :icon="Delete"
            aria-label="删除所选步骤"
            type="danger"
            @click="emit('command', 'delete')"
          />
        </el-tooltip>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">名称</label>
        <el-input v-model="selectedStep.name" placeholder="步骤名称" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">类型</label>
        <el-select
          :model-value="selectedStep.type"
          class="!w-full"
          @update:model-value="emit('update-step-type', $event as StepType)"
        >
          <el-option
            v-for="option in stepTypeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <StepTypeFields
          :step="selectedStep"
          :components="components"
          :allow-component-call="allowComponentCall"
          :get-field-error="getFieldError"
          :get-step-template-options-fn="getStepTemplateOptionsFn"
          :get-step-template-hint-fn="getStepTemplateHintFn"
          :format-component-option-label-fn="formatComponentOptionLabelFn"
        />
        <ConditionalBranchFields
          v-if="selectedStep.type === 'conditional_branch' && selectedNode.kind === 'top-step'"
          :step="selectedStep"
          :templates="templates"
          :get-step-template-options-fn="getStepTemplateOptionsFn"
          :get-step-template-hint-fn="getStepTemplateHintFn"
          @update-step-type="updateBranchChildType"
        />
        <StepRuntimeFields :step="selectedStep" :get-field-error="getFieldError" />
        <StepAdvancedPayloadField
          :step="selectedStep"
          :get-field-error="getFieldError"
        />
      </div>

      <div
        v-if="Object.keys(validationErrors).length > 0"
        class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-700"
        role="status"
      >
        当前步骤有 {{ Object.keys(validationErrors).length }} 个配置错误，节点摘要和错误角标已同步更新。
      </div>
    </div>

    <div v-else-if="selectedBranch" class="space-y-4">
      <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
        分支按显示顺序首个命中后停止。修改 branchKey 会同步迁移画布结构路径。
      </div>
      <div class="grid grid-cols-2 gap-3">
        <ConditionalBranchMetadataFields
          :branch="selectedBranch"
          :template-options="branchTemplateOptions"
          controlled-branch-key
          @update-branch-key="emit('update-branch-key', $event)"
        />
      </div>
    </div>

    <div v-else-if="selectedElseStep" class="space-y-4">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">默认分支名称</label>
        <el-input v-model="selectedElseStep.elseBranchName" placeholder="默认分支" />
      </div>
      <p class="m-0 text-xs leading-5 text-slate-500">
        默认分支在所有条件均未命中时执行。
      </p>
    </div>

    <div v-else class="readonly-card">
      <strong>{{ selectedNode.label }}</strong>
      <span>{{ selectedNode.summary }}</span>
      <span v-if="selectedNode.kind === 'component-preview'">
        组件预览只读，请前往组件管理编辑源组件。
      </span>
      <span v-else>该结构节点没有可编辑的步骤字段。</span>
    </div>
  </template>

  <template v-else-if="activeTab === 'style'">
    <div v-if="selectedEditablePath" class="space-y-5">
      <p class="m-0 text-xs leading-5 text-slate-500">
        样式应用到 {{ selectedCount }} 个所选可编辑节点，仅保存在当前浏览器。
      </p>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">颜色</label>
        <div class="style-palette">
          <el-tooltip
            v-for="color in colorPalette"
            :key="color"
            :content="color"
            placement="top"
          >
            <button
              :aria-label="`使用颜色 ${color}`"
              class="palette-button"
              :class="{ 'is-active': displayNodeState.color === color }"
              :style="{ backgroundColor: color }"
              type="button"
              @click="emit('apply-style', { color })"
            />
          </el-tooltip>
        </div>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">形状</label>
        <el-radio-group
          :model-value="displayNodeState.shape ?? 'rectangle'"
          class="w-full"
          @update:model-value="emit('apply-style', { shape: $event as 'rectangle' | 'rounded' })"
        >
          <el-radio-button value="rectangle">矩形</el-radio-button>
          <el-radio-button value="rounded">圆角</el-radio-button>
        </el-radio-group>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">尺寸</label>
        <el-radio-group
          :model-value="displayNodeState.size ?? 'medium'"
          class="w-full"
          @update:model-value="emit('apply-style', { size: $event as 'small' | 'medium' | 'large' })"
        >
          <el-radio-button value="small">S</el-radio-button>
          <el-radio-button value="medium">M</el-radio-button>
          <el-radio-button value="large">L</el-radio-button>
        </el-radio-group>
      </div>
      <el-button class="w-full" plain @click="emit('reset-style')">
        恢复类型默认样式
      </el-button>
    </div>
    <div v-else class="inspector-empty">
      请选择普通步骤或分支子步骤；根节点和组件预览不支持自定义样式。
    </div>
  </template>

  <template v-else>
    <div v-if="selectedEditablePath" class="space-y-4">
      <div class="rounded-lg border border-sky-200 bg-sky-50 p-3 text-xs leading-5 text-sky-900">
        依赖和并行关系仅作设计标注，不进入保存 payload，也不改变当前顺序执行行为。
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">关系类型</label>
        <el-radio-group v-model="relationKind">
          <el-radio-button value="dependency">依赖</el-radio-button>
          <el-radio-button value="parallel">并行</el-radio-button>
        </el-radio-group>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">目标节点</label>
        <el-select v-model="relationTarget" class="!w-full" filterable>
          <el-option
            v-for="node in relationTargets"
            :key="node.path"
            :label="`${node.stepNo ?? '--'} · ${node.label}`"
            :value="node.path"
          />
        </el-select>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">说明(可选)</label>
        <el-input v-model="relationLabel" maxlength="80" />
      </div>
      <el-tooltip content="仅标注，不影响当前执行顺序" placement="top">
        <el-button
          class="w-full"
          color="#2563eb"
          :disabled="!relationTarget"
          @click="submitAnnotation"
        >
          创建仅标注关系
        </el-button>
      </el-tooltip>

      <div v-if="relatedAnnotations.length > 0" class="space-y-2 border-t border-slate-200 pt-4">
        <strong class="text-sm text-slate-700">相关标注</strong>
        <div
          v-for="annotation in relatedAnnotations"
          :key="annotation.id"
          class="relation-row"
          :title="`${annotation.kind === 'dependency' ? '依赖' : '并行'}，仅标注，不改变执行`"
        >
          <div class="min-w-0">
            <strong>{{ annotation.kind === 'dependency' ? '依赖' : '并行' }} · 仅标注</strong>
            <span>{{ annotation.label || `${annotation.source} → ${annotation.target}` }}</span>
          </div>
          <el-button
            :icon="Delete"
            aria-label="删除标注关系"
            circle
            text
            type="danger"
            @click="emit('delete-annotation', annotation.id)"
          />
        </div>
      </div>
    </div>
    <div v-else class="inspector-empty">
      请选择可编辑步骤作为说明性关系的起点。
    </div>
  </template>
</template>

<style scoped>
.inspector-empty {
  padding: 28px 12px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

.inspector-command-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
}

.inspector-command-row :deep(.el-button) {
  width: 100%;
  margin: 0;
}

:deep(.el-button:focus-visible) {
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 24%);
}

.readonly-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  background: #f8fafc;
  font-size: 12px;
  line-height: 20px;
}

.readonly-card strong {
  color: #1e293b;
  font-size: 14px;
}

.style-palette {
  display: grid;
  grid-template-columns: repeat(7, 28px);
  gap: 8px;
}

.palette-button {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 2px solid #fff;
  border-radius: 6px;
  box-shadow: 0 0 0 1px #cbd5e1;
  cursor: pointer;
}

.palette-button.is-active,
.palette-button:focus-visible {
  box-shadow: 0 0 0 2px #2563eb;
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.relation-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px dashed #94a3b8;
  border-radius: 6px;
  color: #64748b;
  background: #f8fafc;
  font-size: 11px;
}

.relation-row div,
.relation-row strong,
.relation-row span {
  display: block;
  min-width: 0;
}

.relation-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
