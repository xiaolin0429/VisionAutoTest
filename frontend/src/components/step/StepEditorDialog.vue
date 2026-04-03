<script setup lang="ts">
import {
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
  if (props.formatComponentOptionLabelFn) {
    return props.formatComponentOptionLabelFn(component)
  }
  return `${component.name} (#${component.id}) · ${component.status}`
}

function handleClose() {
  emit('update:visible', false)
}

function showLocatorFields(step: StepDraft) {
  if (!supportsOcrLocator(step.type)) {
    return false
  }

  return step.type !== 'scroll' || step.scrollTarget === 'element'
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
