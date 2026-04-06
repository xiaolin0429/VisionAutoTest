<script setup lang="ts">
import BranchChildStepFields from './BranchChildStepFields.vue'
import {
  CONDITIONAL_BRANCH_CONDITION_OPTIONS,
  createBranchChildStepDraft,
  INPUT_MODE_OPTIONS,
  LONG_PRESS_BUTTON_OPTIONS,
  LOCATOR_TYPE_OPTIONS,
  NAVIGATE_WAIT_UNTIL_OPTIONS,
  OCR_MATCH_MODE_OPTIONS,
  OCR_LOCATOR_MATCH_MODE_OPTIONS,
  SCROLL_BEHAVIOR_OPTIONS,
  SCROLL_DIRECTION_OPTIONS,
  SCROLL_TARGET_OPTIONS,
  STEP_TYPE_LABELS,
  supportsOcrLocator,
  type StepDraft,
  type StepValidationErrors
} from '@/utils/steps'
import type { Component, StepType, Template } from '@/types/models'

interface StepTemplateOption {
  id: number
  label: string
}

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

function formatComponentLabel(component: Component) {
  // @param component Component shown in the component-call selector.
  if (props.formatComponentOptionLabelFn) {
    return props.formatComponentOptionLabelFn(component)
  }
  return `${component.name} (#${component.id}) · ${component.status}`
}

function handleClose() {
  // Closes the dialog through the controlled `visible` prop channel.
  emit('update:visible', false)
}

function showLocatorFields(step: StepDraft) {
  // @param step Current step draft whose type and scroll target determine whether locator configuration is meaningful.
  if (!supportsOcrLocator(step.type)) {
    return false
  }

  return step.type !== 'scroll' || step.scrollTarget === 'element'
}

function branchChildTypeOptions() {
  // @returns The restricted step types supported inside conditional-branch child steps.
  return [
    { label: STEP_TYPE_LABELS.wait, value: 'wait' },
    { label: STEP_TYPE_LABELS.click, value: 'click' },
    { label: STEP_TYPE_LABELS.input, value: 'input' },
    { label: STEP_TYPE_LABELS.template_assert, value: 'template_assert' },
    { label: STEP_TYPE_LABELS.ocr_assert, value: 'ocr_assert' },
    { label: STEP_TYPE_LABELS.navigate, value: 'navigate' },
    { label: STEP_TYPE_LABELS.scroll, value: 'scroll' },
    { label: STEP_TYPE_LABELS.long_press, value: 'long_press' }
  ]
}

function updateBranchChildType(step: StepDraft, nextType: string | number | boolean) {
  // @param step Branch child draft being updated.
  // @param nextType Raw select value forwarded to the shared step-type normalization flow.
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
            <el-button
              link
              type="danger"
              @click="emit('remove-step', index)"
            >
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

          <!-- wait -->
          <template v-if="step.type === 'wait'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">等待时长(ms)</label>
              <el-input-number v-model="step.waitMs" :min="0" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'waitMs')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'waitMs') }}
              </p>
            </div>
          </template>

          <!-- click -->
          <template v-if="step.type === 'click'">
            <div v-if="showLocatorFields(step)">
              <label class="mb-2 block text-sm font-medium text-slate-700">定位方式</label>
              <el-select v-model="step.locator" class="!w-full">
                <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </div>
            <div class="col-span-2">
              <template v-if="step.locator === 'selector'">
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input v-model="step.selector" placeholder="例如 [data-testid='submit-button']" />
                <p v-if="getStepErrorFn(index, 'selector')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'selector') }}
                </p>
              </template>
              <template v-else-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">视觉模板</label>
                <el-select v-model="step.visualTemplateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                  <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'visualTemplateId')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualTemplateId') }}
                </p>
                <p v-else-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                  {{ getStepTemplateHintFn!(step) }}
                </p>
              </template>
              <template v-else>
                <label class="mb-2 block text-sm font-medium text-slate-700">OCR 文本</label>
                <el-input v-model="step.ocrText" placeholder="请输入要识别的界面文本" />
                <p v-if="getStepErrorFn(index, 'ocrText')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrText') }}
                </p>
              </template>
            </div>
            <template v-if="step.locator === 'ocr'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                <el-select v-model="step.ocrMatchMode" class="!w-full">
                  <el-option v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'ocrMatchMode')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrMatchMode') }}
                </p>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配序号</label>
                <el-input-number v-model="step.ocrOccurrence" :min="1" class="!w-full" />
                <p v-if="getStepErrorFn(index, 'ocrOccurrence')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrOccurrence') }}
                </p>
              </div>
              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
                <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <el-checkbox v-model="step.ocrCaseSensitive">OCR 文本区分大小写</el-checkbox>
                </div>
              </div>
            </template>
              <div v-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配阈值(可选)</label>
                <el-input-number v-model="step.visualThreshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" placeholder="留空则使用模板默认阈值" />
                <p v-if="getStepErrorFn(index, 'visualThreshold')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualThreshold') }}
                </p>
              </div>
              <div v-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">锚点横向比例</label>
                <el-input-number v-model="step.visualAnchorXRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
                <p class="mt-2 text-xs text-slate-500">0 表示命中区域最左侧，1 表示最右侧，默认 0.50。</p>
                <p v-if="getStepErrorFn(index, 'visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualAnchorXRatio') }}
                </p>
              </div>
              <div v-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">锚点纵向比例</label>
                <el-input-number v-model="step.visualAnchorYRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
                <p class="mt-2 text-xs text-slate-500">0 表示命中区域顶部，1 表示底部，默认 0.50。</p>
                <p v-if="getStepErrorFn(index, 'visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualAnchorYRatio') }}
                </p>
              </div>
          </template>

          <!-- navigate -->
          <template v-if="step.type === 'navigate'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">URL / 相对路径</label>
              <el-input v-model="step.url" placeholder="例如 /login 或 https://example.com/orders/123" />
              <p class="mt-2 text-xs text-slate-500">
                相对路径将基于环境档案 `base_url` 拼接；绝对 URL 将直接访问。
              </p>
              <p v-if="getStepErrorFn(index, 'url')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'url') }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">等待策略</label>
              <el-select v-model="step.waitUntil" class="!w-full">
                <el-option v-for="option in NAVIGATE_WAIT_UNTIL_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'waitUntil')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'waitUntil') }}
              </p>
            </div>
          </template>

          <!-- scroll -->
          <template v-if="step.type === 'scroll'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">滑动目标</label>
              <el-select v-model="step.scrollTarget" class="!w-full">
                <el-option v-for="option in SCROLL_TARGET_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'scrollTarget')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'scrollTarget') }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">滑动方向</label>
              <el-select v-model="step.direction" class="!w-full">
                <el-option v-for="option in SCROLL_DIRECTION_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'direction')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'direction') }}
              </p>
            </div>
            <div v-if="step.scrollTarget === 'element'" class="col-span-2">
              <template v-if="showLocatorFields(step)">
                <label class="mb-2 block text-sm font-medium text-slate-700">定位方式</label>
                <el-select v-model="step.locator" class="!w-full">
                  <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </template>
              <template v-if="step.locator === 'selector'">
                <label class="mb-2 mt-4 block text-sm font-medium text-slate-700">目标元素选择器</label>
                <el-input v-model="step.selector" placeholder="例如 .table-container" />
                <p v-if="getStepErrorFn(index, 'selector')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'selector') }}
                </p>
              </template>
              <template v-else-if="step.locator === 'visual'">
                <label class="mb-2 mt-4 block text-sm font-medium text-slate-700">视觉模板</label>
                <el-select v-model="step.visualTemplateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                  <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'visualTemplateId')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualTemplateId') }}
                </p>
                <p v-else-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                  {{ getStepTemplateHintFn!(step) }}
                </p>
              </template>
              <template v-else>
                <label class="mb-2 mt-4 block text-sm font-medium text-slate-700">OCR 文本</label>
                <el-input v-model="step.ocrText" placeholder="请输入要识别的滑动目标文本" />
                <p v-if="getStepErrorFn(index, 'ocrText')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrText') }}
                </p>
              </template>
              <div v-if="step.locator === 'ocr'" class="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                  <el-select v-model="step.ocrMatchMode" class="!w-full">
                    <el-option v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                  </el-select>
                  <p v-if="getStepErrorFn(index, 'ocrMatchMode')" class="mt-2 text-xs text-rose-600">
                    {{ getStepErrorFn(index, 'ocrMatchMode') }}
                  </p>
                </div>
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">匹配序号</label>
                  <el-input-number v-model="step.ocrOccurrence" :min="1" class="!w-full" />
                  <p v-if="getStepErrorFn(index, 'ocrOccurrence')" class="mt-2 text-xs text-rose-600">
                    {{ getStepErrorFn(index, 'ocrOccurrence') }}
                  </p>
                </div>
                <div class="col-span-2">
                  <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
                  <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                    <el-checkbox v-model="step.ocrCaseSensitive">OCR 文本区分大小写</el-checkbox>
                  </div>
                </div>
              </div>
              <div v-if="step.locator === 'visual'" class="mt-4">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配阈值(可选)</label>
                <el-input-number v-model="step.visualThreshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" placeholder="留空则使用模板默认阈值" />
                <p v-if="getStepErrorFn(index, 'visualThreshold')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualThreshold') }}
                </p>
              </div>
              <div v-if="step.locator === 'visual'" class="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">锚点横向比例</label>
                  <el-input-number v-model="step.visualAnchorXRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
                  <p v-if="getStepErrorFn(index, 'visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">
                    {{ getStepErrorFn(index, 'visualAnchorXRatio') }}
                  </p>
                </div>
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">锚点纵向比例</label>
                  <el-input-number v-model="step.visualAnchorYRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
                  <p v-if="getStepErrorFn(index, 'visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">
                    {{ getStepErrorFn(index, 'visualAnchorYRatio') }}
                  </p>
                </div>
              </div>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">滑动距离(px)</label>
              <el-input-number v-model="step.distance" :min="1" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'distance')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'distance') }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">滑动行为</label>
              <el-select v-model="step.behavior" class="!w-full">
                <el-option v-for="option in SCROLL_BEHAVIOR_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'behavior')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'behavior') }}
              </p>
            </div>
          </template>

          <!-- long_press -->
          <template v-if="step.type === 'long_press'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">定位方式</label>
              <el-select v-model="step.locator" class="!w-full">
                <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">长按时长(ms)</label>
              <el-input-number v-model="step.durationMs" :min="1" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'durationMs')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'durationMs') }}
              </p>
            </div>
            <div class="col-span-2">
              <template v-if="step.locator === 'selector'">
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input v-model="step.selector" placeholder="例如 [data-testid='card']" />
                <p v-if="getStepErrorFn(index, 'selector')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'selector') }}
                </p>
              </template>
              <template v-else-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">视觉模板</label>
                <el-select v-model="step.visualTemplateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                  <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'visualTemplateId')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualTemplateId') }}
                </p>
                <p v-else-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                  {{ getStepTemplateHintFn!(step) }}
                </p>
              </template>
              <template v-else>
                <label class="mb-2 block text-sm font-medium text-slate-700">OCR 文本</label>
                <el-input v-model="step.ocrText" placeholder="请输入要识别的界面文本" />
                <p v-if="getStepErrorFn(index, 'ocrText')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrText') }}
                </p>
              </template>
            </div>
            <template v-if="step.locator === 'ocr'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                <el-select v-model="step.ocrMatchMode" class="!w-full">
                  <el-option v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'ocrMatchMode')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrMatchMode') }}
                </p>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配序号</label>
                <el-input-number v-model="step.ocrOccurrence" :min="1" class="!w-full" />
                <p v-if="getStepErrorFn(index, 'ocrOccurrence')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrOccurrence') }}
                </p>
              </div>
              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
                <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <el-checkbox v-model="step.ocrCaseSensitive">OCR 文本区分大小写</el-checkbox>
                </div>
              </div>
            </template>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">匹配阈值(可选)</label>
              <el-input-number v-model="step.visualThreshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" placeholder="留空则使用模板默认阈值" />
              <p v-if="getStepErrorFn(index, 'visualThreshold')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualThreshold') }}
              </p>
            </div>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">锚点横向比例</label>
              <el-input-number v-model="step.visualAnchorXRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualAnchorXRatio') }}
              </p>
            </div>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">锚点纵向比例</label>
              <el-input-number v-model="step.visualAnchorYRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualAnchorYRatio') }}
              </p>
            </div>
            <div class="col-span-2">
              <label class="mb-2 block text-sm font-medium text-slate-700">按钮类型</label>
              <el-select v-model="step.button" class="!w-full">
                <el-option v-for="option in LONG_PRESS_BUTTON_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p class="mt-2 text-xs text-slate-500">首期固定支持 `left`，用于覆盖常见 Web UI 与 H5 长按场景。</p>
              <p v-if="getStepErrorFn(index, 'button')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'button') }}
              </p>
            </div>
          </template>

          <!-- input -->
          <template v-if="step.type === 'input'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">定位方式</label>
              <el-select v-model="step.locator" class="!w-full">
                <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">输入方式</label>
              <el-select v-model="step.inputMode" class="!w-full">
                <el-option v-for="option in INPUT_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'inputMode')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'inputMode') }}
              </p>
            </div>
            <div class="col-span-2">
              <label class="mb-2 block text-sm font-medium text-slate-700">输入文本</label>
              <el-input v-model="step.text" placeholder="请输入要填充的内容" />
              <p v-if="getStepErrorFn(index, 'text')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'text') }}
              </p>
            </div>
            <div class="col-span-2">
              <template v-if="step.locator === 'selector'">
                <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                <el-input v-model="step.selector" placeholder="例如 [data-testid='name-input']" />
                <p v-if="getStepErrorFn(index, 'selector')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'selector') }}
                </p>
              </template>
              <template v-else-if="step.locator === 'visual'">
                <label class="mb-2 block text-sm font-medium text-slate-700">视觉模板</label>
                <el-select v-model="step.visualTemplateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                  <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'visualTemplateId')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'visualTemplateId') }}
                </p>
                <p v-else-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                  {{ getStepTemplateHintFn!(step) }}
                </p>
              </template>
              <template v-else>
                <label class="mb-2 block text-sm font-medium text-slate-700">OCR 文本</label>
                <el-input v-model="step.ocrText" placeholder="请输入要识别的输入框附近文本" />
                <p v-if="getStepErrorFn(index, 'ocrText')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrText') }}
                </p>
              </template>
            </div>
            <template v-if="step.locator === 'ocr'">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                <el-select v-model="step.ocrMatchMode" class="!w-full">
                  <el-option v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
                <p v-if="getStepErrorFn(index, 'ocrMatchMode')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrMatchMode') }}
                </p>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配序号</label>
                <el-input-number v-model="step.ocrOccurrence" :min="1" class="!w-full" />
                <p v-if="getStepErrorFn(index, 'ocrOccurrence')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'ocrOccurrence') }}
                </p>
              </div>
              <div class="col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
                <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <el-checkbox v-model="step.ocrCaseSensitive">OCR 文本区分大小写</el-checkbox>
                </div>
              </div>
            </template>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">匹配阈值(可选)</label>
              <el-input-number v-model="step.visualThreshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" placeholder="留空则使用模板默认阈值" />
              <p v-if="getStepErrorFn(index, 'visualThreshold')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualThreshold') }}
              </p>
            </div>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">锚点横向比例</label>
              <el-input-number v-model="step.visualAnchorXRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualAnchorXRatio') }}
              </p>
            </div>
            <div v-if="step.locator === 'visual'">
              <label class="mb-2 block text-sm font-medium text-slate-700">锚点纵向比例</label>
              <el-input-number v-model="step.visualAnchorYRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'visualAnchorYRatio') }}
              </p>
            </div>
            <div v-if="step.inputMode === 'otp'">
              <label class="mb-2 block text-sm font-medium text-slate-700">验证码长度</label>
              <el-input-number v-model="step.otpLength" :min="1" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'otpLength')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'otpLength') }}
              </p>
            </div>
            <div v-if="step.inputMode !== 'fill'">
              <label class="mb-2 block text-sm font-medium text-slate-700">逐字符延迟(ms)</label>
              <el-input-number v-model="step.perCharDelayMs" :min="0" class="!w-full" />
              <p v-if="getStepErrorFn(index, 'perCharDelayMs')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'perCharDelayMs') }}
              </p>
            </div>
          </template>

          <!-- template_assert -->
          <template v-if="step.type === 'template_assert'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">模板选择</label>
              <el-select v-model="step.templateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'templateId')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'templateId') }}
              </p>
              <p v-else-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                {{ getStepTemplateHintFn!(step) }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">阈值(可选)</label>
              <el-input-number v-model="step.threshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" placeholder="留空则使用模板默认阈值" />
              <p v-if="getStepErrorFn(index, 'threshold')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'threshold') }}
              </p>
            </div>
          </template>

          <!-- ocr_assert -->
          <template v-if="step.type === 'ocr_assert'">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">OCR 模板(可选)</label>
              <el-select v-model="step.templateId" class="!w-full" clearable placeholder="可选，需为 ocr 策略模板">
                <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
              </el-select>
              <p v-if="getStepTemplateHintFn?.(step)" class="mt-2 text-xs text-amber-600">
                {{ getStepTemplateHintFn!(step) }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
              <el-input v-model="step.selector" placeholder="例如 [data-testid='result-banner']" />
              <p v-if="getStepErrorFn(index, 'selector')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'selector') }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">期望文本</label>
              <el-input v-model="step.expectedText" placeholder="请输入 OCR 期望结果" />
              <p v-if="getStepErrorFn(index, 'expectedText')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'expectedText') }}
              </p>
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
              <el-select v-model="step.matchMode" class="!w-full">
                <el-option v-for="option in OCR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'matchMode')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'matchMode') }}
              </p>
            </div>
            <div class="col-span-2">
              <label class="mb-2 block text-sm font-medium text-slate-700">匹配选项</label>
              <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                <el-checkbox v-model="step.caseSensitive">OCR 结果区分大小写</el-checkbox>
              </div>
            </div>
          </template>

          <!-- component_call -->
          <template v-if="step.type === 'component_call' && allowComponentCall">
            <div class="col-span-2">
              <label class="mb-2 block text-sm font-medium text-slate-700">组件选择</label>
              <el-select v-model="step.componentId" class="!w-full" clearable placeholder="请选择组件">
                <el-option v-for="item in components" :key="item.id" :label="formatComponentLabel(item)" :value="item.id" />
              </el-select>
              <p v-if="getStepErrorFn(index, 'componentId')" class="mt-2 text-xs text-rose-600">
                {{ getStepErrorFn(index, 'componentId') }}
              </p>
            </div>
          </template>

          <!-- conditional_branch -->
          <template v-if="step.type === 'conditional_branch'">
            <div class="col-span-2 space-y-4">
              <div class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <p class="m-0 font-medium">条件分支步骤说明</p>
                <p class="mb-0 mt-2 leading-6">
                  分支按顺序匹配，命中第一个后停止。本期支持 `ocr_text_visible`、`template_visible`、`selector_exists`。
                </p>
                <p class="mb-0 mt-2 leading-6">
                  分支子步骤请填写 JSON 数组，每项结构应与后端契约一致；子步骤不支持 `component_call` 和嵌套 `conditional_branch`。
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
                  <div>
                    <label class="mb-2 block text-sm font-medium text-slate-700">branchKey</label>
                    <el-input v-model="branch.branchKey" placeholder="例如 branch_a" />
                  </div>
                  <div>
                    <label class="mb-2 block text-sm font-medium text-slate-700">分支名称</label>
                    <el-input v-model="branch.branchName" placeholder="例如 显示A时执行" />
                  </div>
                  <div>
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
                    <div>
                      <label class="mb-2 block text-sm font-medium text-slate-700">期望文本</label>
                      <el-input v-model="branch.expectedText" placeholder="请输入 OCR 文本" />
                    </div>
                    <div>
                      <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
                      <el-select v-model="branch.matchMode" class="!w-full">
                        <el-option v-for="option in OCR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
                      </el-select>
                    </div>
                    <div class="col-span-2">
                      <div class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                        <el-checkbox v-model="branch.caseSensitive">区分大小写</el-checkbox>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="branch.conditionType === 'template_visible'">
                    <div>
                      <label class="mb-2 block text-sm font-medium text-slate-700">模板</label>
                      <el-select v-model="branch.templateId" class="!w-full" clearable placeholder="请选择 template 策略模板">
                        <el-option v-for="option in templates.filter((item) => item.matchStrategy === 'template').map((item) => ({ id: item.id, label: `${item.name} (#${item.id})` }))" :key="option.id" :label="option.label" :value="option.id" />
                      </el-select>
                    </div>
                    <div>
                      <label class="mb-2 block text-sm font-medium text-slate-700">阈值(可选)</label>
                      <el-input-number v-model="branch.threshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" />
                    </div>
                  </template>

                  <template v-else>
                    <div class="col-span-2">
                      <label class="mb-2 block text-sm font-medium text-slate-700">选择器</label>
                      <el-input v-model="branch.selector" placeholder="例如 .banner-success" />
                    </div>
                  </template>

                  <div class="col-span-2">
                    <div class="mb-2 flex items-center justify-between gap-3">
                      <label class="block text-sm font-medium text-slate-700">分支子步骤</label>
                      <el-button plain size="small" @click="branch.steps.push(createBranchChildStepDraft(branch.steps.length))">
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
                        :child-type-options="branchChildTypeOptions()"
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
                  @click="step.conditionalBranches.push({ id: -Date.now(), branchKey: `branch_${step.conditionalBranches.length + 1}`, branchName: `分支 ${step.conditionalBranches.length + 1}`, conditionType: 'ocr_text_visible', expectedText: '', matchMode: 'contains', caseSensitive: false, templateId: null, threshold: null, selector: '', steps: [createBranchChildStepDraft(0)] })"
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
                      <el-button plain size="small" @click="step.elseSteps.push(createBranchChildStepDraft(step.elseSteps.length))">
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
                        :child-type-options="branchChildTypeOptions()"
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

          <!-- common: timeout + retry -->
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">超时时间(ms)</label>
            <el-input-number v-model="step.timeoutMs" :min="1" class="!w-full" />
            <p v-if="getStepErrorFn(index, 'timeoutMs')" class="mt-2 text-xs text-rose-600">
              {{ getStepErrorFn(index, 'timeoutMs') }}
            </p>
          </div>
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-700">重试次数</label>
            <el-input-number v-model="step.retryTimes" :min="0" class="!w-full" />
            <p v-if="getStepErrorFn(index, 'retryTimes')" class="mt-2 text-xs text-rose-600">
              {{ getStepErrorFn(index, 'retryTimes') }}
            </p>
          </div>

          <!-- advanced payload -->
          <div class="col-span-2">
            <details :open="shouldOpenAdvancedPayloadFn(index)" class="rounded-2xl border border-slate-200 bg-white">
              <summary class="cursor-pointer list-none px-4 py-3 text-sm font-medium text-slate-700">
                高级 payload 配置
              </summary>
              <div class="border-t border-slate-200 px-4 py-4">
                <p class="m-0 text-sm leading-6 text-slate-500">
                  这里填写额外 payload JSON。已提供的结构化字段会在保存时自动覆盖同名键。
                </p>
                <el-input v-model="step.extraPayloadJson" :rows="5" class="!mt-3" type="textarea" />
                <p v-if="getStepErrorFn(index, 'extraPayloadJson')" class="mt-2 text-xs text-rose-600">
                  {{ getStepErrorFn(index, 'extraPayloadJson') }}
                </p>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="handleClose">取消</el-button>
        <el-button :loading="savingSteps" color="#2563eb" @click="emit('save')">保存步骤</el-button>
      </div>
    </template>
  </el-dialog>
</template>
