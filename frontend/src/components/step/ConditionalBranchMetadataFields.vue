<script setup lang="ts">
import OcrTargetFields from './OcrTargetFields.vue'
import {
  CONDITIONAL_BRANCH_CONDITION_OPTIONS,
  type ConditionalBranchDraft,
  type StepTemplateOption
} from '@/utils/steps'

const props = withDefaults(defineProps<{
  branch: ConditionalBranchDraft
  templateOptions: StepTemplateOption[]
  controlledBranchKey?: boolean
}>(), {
  controlledBranchKey: false
})

const emit = defineEmits<{
  (event: 'update-branch-key', value: string): void
}>()

function updateBranchKey(value: string): void {
  if (props.controlledBranchKey) {
    emit('update-branch-key', value)
    return
  }
  props.branch.branchKey = value
}
</script>

<template>
  <div>
    <label class="mb-2 block text-sm font-medium text-slate-700">branchKey</label>
    <el-input
      :model-value="branch.branchKey"
      placeholder="例如 branch_a"
      @update:model-value="updateBranchKey"
    />
  </div>
  <div>
    <label class="mb-2 block text-sm font-medium text-slate-700">分支名称</label>
    <el-input v-model="branch.branchName" placeholder="例如 显示 A 时执行" />
  </div>
  <div class="col-span-2">
    <label class="mb-2 block text-sm font-medium text-slate-700">条件类型</label>
    <el-select v-model="branch.conditionType" class="!w-full">
      <el-option
        v-for="option in CONDITIONAL_BRANCH_CONDITION_OPTIONS"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
  </div>

  <template v-if="branch.conditionType === 'ocr_text_visible'">
    <OcrTargetFields
      :target="branch.ocrTarget"
      title="条件目标"
      :show-action-point="false"
    />
  </template>

  <template v-else-if="branch.conditionType === 'template_visible'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">模板</label>
      <el-select
        v-model="branch.templateId"
        class="!w-full"
        clearable
        placeholder="请选择 template 策略模板"
      >
        <el-option
          v-for="option in templateOptions"
          :key="option.id"
          :label="option.label"
          :value="option.id"
        />
      </el-select>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">阈值(可选)</label>
      <el-input-number
        v-model="branch.threshold"
        :max="1"
        :min="0"
        :precision="2"
        :step="0.01"
        :value-on-clear="null"
        class="!w-full"
      />
    </div>
  </template>

  <template v-else>
    <div class="col-span-2">
      <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
      <el-input v-model="branch.selector" placeholder="例如 .banner-success" />
    </div>
  </template>
</template>
