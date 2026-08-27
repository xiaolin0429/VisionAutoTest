<script setup lang="ts">
import StepAdvancedPayloadField from './StepAdvancedPayloadField.vue'
import StepRuntimeFields from './StepRuntimeFields.vue'
import StepTypeFields from './StepTypeFields.vue'
import {
  STEP_TYPE_LABELS,
  validateStepDraft,
  type StepDraft,
  type StepTemplateOption,
  type StepValidationErrors
} from '@/utils/steps'
import type { Template } from '@/types/models'

const props = withDefaults(
  defineProps<{
    step: StepDraft
    indexLabel: string
    templates?: Template[]
    getStepTemplateOptionsFn: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
    childTypeOptions: Array<{ label: string; value: string }>
  }>(),
  {
    templates: () => [],
    getStepTemplateHintFn: undefined
  }
)

const emit = defineEmits<{
  (event: 'remove'): void
  (event: 'update-step-type', step: StepDraft, value: string | number | boolean): void
}>()

function getFieldError(field: keyof StepValidationErrors): string {
  return validateStepDraft(props.step)[field] ?? ''
}
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-slate-50 p-3">
    <div class="mb-3 flex items-center justify-between gap-3">
      <p class="m-0 text-sm font-medium text-slate-800">{{ indexLabel }}</p>
      <el-button link type="danger" @click="emit('remove')">删除</el-button>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">名称</label>
        <el-input v-model="step.name" :placeholder="STEP_TYPE_LABELS[step.type]" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">类型</label>
        <el-select
          :model-value="step.type"
          class="!w-full"
          @update:model-value="emit('update-step-type', step, $event)"
        >
          <el-option
            v-for="option in childTypeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>

      <StepTypeFields
        :step="step"
        :allow-component-call="false"
        :get-field-error="getFieldError"
        :get-step-template-options-fn="getStepTemplateOptionsFn"
        :get-step-template-hint-fn="getStepTemplateHintFn"
      />
      <StepRuntimeFields :step="step" :get-field-error="getFieldError" />
      <StepAdvancedPayloadField
        :step="step"
        :get-field-error="getFieldError"
        :collapsible="false"
      />
    </div>
  </div>
</template>
