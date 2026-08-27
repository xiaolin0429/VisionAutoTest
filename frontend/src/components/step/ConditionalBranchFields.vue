<script setup lang="ts">
import BranchChildStepFields from './BranchChildStepFields.vue'
import ConditionalBranchMetadataFields from './ConditionalBranchMetadataFields.vue'
import {
  createBranchChildStepDraft,
  createOcrTargetDraft,
  STEP_TYPE_LABELS,
  type ConditionalBranchDraft,
  type StepDraft,
  type StepTemplateOption,
  type StepTypeOption
} from '@/utils/steps'
import type { Template } from '@/types/models'

const props = withDefaults(
  defineProps<{
    step: StepDraft
    templates?: Template[]
    getStepTemplateOptionsFn: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
  }>(),
  {
    templates: () => [],
    getStepTemplateHintFn: undefined
  }
)

const emit = defineEmits<{
  (event: 'update-step-type', step: StepDraft, value: string | number | boolean): void
}>()

const childTypeOptions: StepTypeOption[] = [
  { label: STEP_TYPE_LABELS.wait, value: 'wait' },
  { label: STEP_TYPE_LABELS.click, value: 'click' },
  { label: STEP_TYPE_LABELS.input, value: 'input' },
  { label: STEP_TYPE_LABELS.select_option, value: 'select_option' },
  { label: STEP_TYPE_LABELS.template_assert, value: 'template_assert' },
  { label: STEP_TYPE_LABELS.ocr_assert, value: 'ocr_assert' },
  { label: STEP_TYPE_LABELS.navigate, value: 'navigate' },
  { label: STEP_TYPE_LABELS.scroll, value: 'scroll' },
  { label: STEP_TYPE_LABELS.long_press, value: 'long_press' }
]

function addConditionalBranch(): void {
  const index = props.step.conditionalBranches.length
  const branch: ConditionalBranchDraft = {
    id: -Date.now(),
    branchKey: `branch_${index + 1}`,
    branchName: `分支 ${index + 1}`,
    conditionType: 'ocr_text_visible',
    ocrTarget: createOcrTargetDraft(),
    templateId: null,
    threshold: null,
    selector: '',
    steps: [createBranchChildStepDraft(0)]
  }
  props.step.conditionalBranches.push(branch)
}

function addChildStep(steps: StepDraft[]): void {
  steps.push(createBranchChildStepDraft(steps.length))
}

function getBranchTemplateOptions(): StepTemplateOption[] {
  return props.templates
    .filter((item: Template) => item.matchStrategy === 'template')
    .map((item: Template) => ({
      id: item.id,
      label: `${item.name} (#${item.id})`
    }))
}

function updateBranchChildType(
  step: StepDraft,
  nextType: string | number | boolean
): void {
  emit('update-step-type', step, nextType)
}
</script>

<template>
  <div class="col-span-2 space-y-4">
    <div class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <p class="m-0 font-medium">条件分支步骤说明</p>
      <p class="mb-0 mt-2 leading-6">
        分支按顺序匹配，命中第一个后停止。本期支持 `ocr_text_visible`、`template_visible`、`selector_exists`。
      </p>
      <p class="mb-0 mt-2 leading-6">
        分支子步骤不支持 `component_call` 和嵌套 `conditional_branch`。
      </p>
    </div>

    <div
      v-for="(branch, branchIndex) in step.conditionalBranches"
      :key="branch.id"
      class="rounded-2xl border border-slate-200 bg-white p-4"
    >
      <div class="mb-3 flex items-center justify-between gap-3">
        <p class="m-0 text-sm font-semibold text-slate-900">分支 {{ branchIndex + 1 }}</p>
        <el-button
          v-if="step.conditionalBranches.length > 1"
          link
          type="danger"
          @click="step.conditionalBranches.splice(branchIndex, 1)"
        >
          删除分支
        </el-button>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <ConditionalBranchMetadataFields
          :branch="branch"
          :template-options="getBranchTemplateOptions()"
        />

        <div class="col-span-2">
          <div class="mb-2 flex items-center justify-between gap-3">
            <label class="block text-sm font-medium text-slate-700">分支子步骤</label>
            <el-button plain size="small" @click="addChildStep(branch.steps)">
              新增子步骤
            </el-button>
          </div>
          <div class="space-y-3">
            <BranchChildStepFields
              v-for="(childStep, childIndex) in branch.steps"
              :key="childStep.id"
              :step="childStep"
              :index-label="`子步骤 ${childIndex + 1}`"
              :templates="templates"
              :child-type-options="childTypeOptions"
              :get-step-template-options-fn="getStepTemplateOptionsFn"
              :get-step-template-hint-fn="getStepTemplateHintFn"
              @remove="branch.steps.splice(childIndex, 1)"
              @update-step-type="updateBranchChildType"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="flex justify-between gap-3">
      <el-button
        plain
        :disabled="step.conditionalBranches.length >= 3"
        @click="addConditionalBranch"
      >
        新增分支
      </el-button>
      <div class="text-xs text-slate-500">最多 3 个条件分支</div>
    </div>

    <div class="rounded-2xl border border-slate-200 bg-white p-4">
      <div class="mb-3 flex items-center justify-between gap-3">
        <p class="m-0 text-sm font-semibold text-slate-900">默认分支</p>
        <el-switch v-model="step.elseBranchEnabled" />
      </div>
      <div v-if="step.elseBranchEnabled" class="grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">默认分支名称</label>
          <el-input v-model="step.elseBranchName" placeholder="默认分支" />
        </div>
        <div class="col-span-2">
          <div class="mb-2 flex items-center justify-between gap-3">
            <label class="block text-sm font-medium text-slate-700">默认分支子步骤</label>
            <el-button plain size="small" @click="addChildStep(step.elseSteps)">
              新增子步骤
            </el-button>
          </div>
          <div class="space-y-3">
            <BranchChildStepFields
              v-for="(childStep, childIndex) in step.elseSteps"
              :key="childStep.id"
              :step="childStep"
              :index-label="`默认子步骤 ${childIndex + 1}`"
              :templates="templates"
              :child-type-options="childTypeOptions"
              :get-step-template-options-fn="getStepTemplateOptionsFn"
              :get-step-template-hint-fn="getStepTemplateHintFn"
              @remove="step.elseSteps.splice(childIndex, 1)"
              @update-step-type="updateBranchChildType"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
