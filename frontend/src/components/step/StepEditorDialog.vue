<script setup lang="ts">
import ConditionalBranchFields from './ConditionalBranchFields.vue'
import StepAdvancedPayloadField from './StepAdvancedPayloadField.vue'
import StepRuntimeFields from './StepRuntimeFields.vue'
import StepTypeFields from './StepTypeFields.vue'
import {
  STEP_TYPE_LABELS,
  type StepDraft,
  type StepFieldErrorGetter,
  type StepTemplateOption,
  type StepValidationErrors
} from '@/utils/steps'
import type { Component, StepType, Template } from '@/types/models'

const props = withDefaults(
  defineProps<{
    visible: boolean
    title?: string
    stepDrafts: StepDraft[]
    savingSteps: boolean
    stepSubmitAttempted: boolean
    hasStepValidationErrors: boolean
    stepTypeOptions: Array<{ label: string; value: StepType }>
    templates?: Template[]
    components?: Component[]
    allowComponentCall?: boolean
    getStepErrorFn: (index: number, field: keyof StepValidationErrors) => string
    shouldOpenAdvancedPayloadFn: (index: number) => boolean
    getStepTemplateOptionsFn: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
    formatComponentOptionLabelFn?: (component: Component) => string
  }>(),
  {
    title: '步骤编排',
    templates: () => [],
    components: () => [],
    allowComponentCall: false,
    getStepTemplateHintFn: undefined,
    formatComponentOptionLabelFn: undefined
  }
)

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'add-step'): void
  (event: 'remove-step', index: number): void
  (event: 'move-step', index: number, direction: -1 | 1): void
  (event: 'update-step-type', step: StepDraft, value: string | number | boolean): void
  (event: 'save'): void
  (event: 'closed'): void
}>()

function handleClose(): void {
  emit('update:visible', false)
}

function getFieldError(index: number): StepFieldErrorGetter {
  return (field: keyof StepValidationErrors): string => props.getStepErrorFn(index, field)
}

function updateBranchChildType(
  step: StepDraft,
  nextType: string | number | boolean
): void {
  emit('update-step-type', step, nextType)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    top="4vh"
    width="960px"
    @update:model-value="emit('update:visible', $event)"
    @closed="emit('closed')"
  >
    <div class="mb-4 flex items-start justify-between gap-4">
      <p class="m-0 text-sm leading-6 text-slate-500">
        默认使用结构化表单完成九类常用步骤配置；若有扩展需求，可在每个步骤卡片里展开"高级 payload 配置"。
      </p>
      <el-button plain @click="emit('add-step')">
        新增步骤
      </el-button>
    </div>

    <div
      v-if="stepSubmitAttempted && hasStepValidationErrors"
      class="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
    >
      请修正步骤配置后再保存。
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
              类型：{{ STEP_TYPE_LABELS[step.type] }}，顺序会在保存时自动归一化。
            </p>
          </div>
          <div class="flex gap-2">
            <el-button plain @click="emit('move-step', index, -1)">
              上移
            </el-button>
            <el-button plain @click="emit('move-step', index, 1)">
              下移
            </el-button>
            <el-button link type="danger" @click="emit('remove-step', index)">
              删除
            </el-button>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">步骤名称</label>
            <el-input
              v-model="step.name"
              :placeholder="`${STEP_TYPE_LABELS[step.type]} ${step.stepNo}`"
            />
          </div>

          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">步骤类型</label>
            <el-select
              :model-value="step.type"
              class="!w-full"
              @update:model-value="emit('update-step-type', step, $event)"
            >
              <el-option
                v-for="option in stepTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>

          <StepTypeFields
            :step="step"
            :components="components"
            :allow-component-call="allowComponentCall"
            :get-field-error="getFieldError(index)"
            :get-step-template-options-fn="getStepTemplateOptionsFn"
            :get-step-template-hint-fn="getStepTemplateHintFn"
            :format-component-option-label-fn="formatComponentOptionLabelFn"
          />

          <ConditionalBranchFields
            v-if="step.type === 'conditional_branch'"
            :step="step"
            :templates="templates"
            :get-step-template-options-fn="getStepTemplateOptionsFn"
            :get-step-template-hint-fn="getStepTemplateHintFn"
            @update-step-type="updateBranchChildType"
          />

          <StepRuntimeFields
            :step="step"
            :get-field-error="getFieldError(index)"
          />
          <StepAdvancedPayloadField
            :step="step"
            :get-field-error="getFieldError(index)"
            :open="shouldOpenAdvancedPayloadFn(index)"
          />
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="handleClose">取消</el-button>
        <el-button :loading="savingSteps" color="#2563eb" @click="emit('save')">
          保存步骤
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
