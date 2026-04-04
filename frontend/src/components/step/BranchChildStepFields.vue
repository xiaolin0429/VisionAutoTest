<script setup lang="ts">
import {
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
  validateStepDraft,
  type StepDraft,
  type StepValidationErrors
} from '@/utils/steps'
import type { Template } from '@/types/models'

interface StepTemplateOption {
  id: number
  label: string
}

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

function showLocatorFields(step: StepDraft) {
  if (!supportsOcrLocator(step.type)) {
    return false
  }

  return step.type !== 'scroll' || step.scrollTarget === 'element'
}

function getFieldError(field: keyof StepValidationErrors) {
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
        <label class="mb-2 block text-xs font-medium text-slate-700">名称</label>
        <el-input v-model="step.name" :placeholder="`${STEP_TYPE_LABELS[step.type]}`" />
      </div>
      <div>
        <label class="mb-2 block text-xs font-medium text-slate-700">类型</label>
        <el-select :model-value="step.type" class="!w-full" @update:model-value="emit('update-step-type', step, $event)">
          <el-option v-for="option in childTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </div>

      <template v-if="step.type === 'wait'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">等待时长(ms)</label>
          <el-input-number v-model="step.waitMs" :min="0" class="!w-full" />
          <p v-if="getFieldError('waitMs')" class="mt-2 text-xs text-rose-600">{{ getFieldError('waitMs') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'click'">
        <div v-if="showLocatorFields(step)">
          <label class="mb-2 block text-xs font-medium text-slate-700">定位方式</label>
          <el-select v-model="step.locator" class="!w-full">
            <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </div>
        <div class="col-span-2">
          <template v-if="step.locator === 'selector'">
            <label class="mb-2 block text-xs font-medium text-slate-700">选择器</label>
            <el-input v-model="step.selector" placeholder="例如 .btn-primary" />
            <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">{{ getFieldError('selector') }}</p>
          </template>
          <template v-else-if="step.locator === 'visual'">
            <label class="mb-2 block text-xs font-medium text-slate-700">视觉模板</label>
            <el-select v-model="step.visualTemplateId" class="!w-full" clearable>
              <el-option v-for="option in getStepTemplateOptionsFn(step)
                " :key="option.id" :label="option.label" :value="option.id" />
            </el-select>
            <p v-if="getFieldError('visualTemplateId')" class="mt-2 text-xs text-rose-600">{{ getFieldError('visualTemplateId') }}</p>
          </template>
          <template v-else>
            <label class="mb-2 block text-xs font-medium text-slate-700">OCR 文本</label>
            <el-input v-model="step.ocrText" />
            <p v-if="getFieldError('ocrText')" class="mt-2 text-xs text-rose-600">{{ getFieldError('ocrText') }}</p>
          </template>
        </div>
        <template v-if="step.locator === 'ocr'">
          <div>
            <label class="mb-2 block text-xs font-medium text-slate-700">匹配模式</label>
            <el-select v-model="step.ocrMatchMode" class="!w-full">
              <el-option v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <p v-if="getFieldError('ocrMatchMode')" class="mt-2 text-xs text-rose-600">{{ getFieldError('ocrMatchMode') }}</p>
          </div>
          <div>
            <label class="mb-2 block text-xs font-medium text-slate-700">匹配序号</label>
            <el-input-number v-model="step.ocrOccurrence" :min="1" class="!w-full" />
            <p v-if="getFieldError('ocrOccurrence')" class="mt-2 text-xs text-rose-600">{{ getFieldError('ocrOccurrence') }}</p>
          </div>
        </template>
        <template v-if="step.locator === 'visual'">
          <div>
            <label class="mb-2 block text-xs font-medium text-slate-700">匹配阈值</label>
            <el-input-number v-model="step.visualThreshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" />
            <p v-if="getFieldError('visualThreshold')" class="mt-2 text-xs text-rose-600">{{ getFieldError('visualThreshold') }}</p>
          </div>
          <div>
            <label class="mb-2 block text-xs font-medium text-slate-700">锚点横向比例</label>
            <el-input-number v-model="step.visualAnchorXRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
            <p v-if="getFieldError('visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">{{ getFieldError('visualAnchorXRatio') }}</p>
          </div>
          <div>
            <label class="mb-2 block text-xs font-medium text-slate-700">锚点纵向比例</label>
            <el-input-number v-model="step.visualAnchorYRatio" :max="1" :min="0" :precision="2" :step="0.01" class="!w-full" />
            <p v-if="getFieldError('visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">{{ getFieldError('visualAnchorYRatio') }}</p>
          </div>
        </template>
      </template>

      <template v-if="step.type === 'input'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">定位方式</label>
          <el-select v-model="step.locator" class="!w-full">
            <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">输入方式</label>
          <el-select v-model="step.inputMode" class="!w-full">
            <el-option v-for="option in INPUT_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('inputMode')" class="mt-2 text-xs text-rose-600">{{ getFieldError('inputMode') }}</p>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-xs font-medium text-slate-700">输入文本</label>
          <el-input v-model="step.text" />
          <p v-if="getFieldError('text')" class="mt-2 text-xs text-rose-600">{{ getFieldError('text') }}</p>
        </div>
        <div class="col-span-2">
          <template v-if="step.locator === 'selector'">
            <label class="mb-2 block text-xs font-medium text-slate-700">选择器</label>
            <el-input v-model="step.selector" />
            <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">{{ getFieldError('selector') }}</p>
          </template>
          <template v-else-if="step.locator === 'visual'">
            <label class="mb-2 block text-xs font-medium text-slate-700">视觉模板</label>
            <el-select v-model="step.visualTemplateId" class="!w-full" clearable>
              <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
            </el-select>
            <p v-if="getFieldError('visualTemplateId')" class="mt-2 text-xs text-rose-600">{{ getFieldError('visualTemplateId') }}</p>
          </template>
          <template v-else>
            <label class="mb-2 block text-xs font-medium text-slate-700">OCR 文本</label>
            <el-input v-model="step.ocrText" />
            <p v-if="getFieldError('ocrText')" class="mt-2 text-xs text-rose-600">{{ getFieldError('ocrText') }}</p>
          </template>
        </div>
        <div v-if="step.inputMode === 'otp'">
          <label class="mb-2 block text-xs font-medium text-slate-700">验证码长度</label>
          <el-input-number v-model="step.otpLength" :min="1" class="!w-full" />
          <p v-if="getFieldError('otpLength')" class="mt-2 text-xs text-rose-600">{{ getFieldError('otpLength') }}</p>
        </div>
        <div v-if="step.inputMode !== 'fill'">
          <label class="mb-2 block text-xs font-medium text-slate-700">逐字符延迟(ms)</label>
          <el-input-number v-model="step.perCharDelayMs" :min="0" class="!w-full" />
          <p v-if="getFieldError('perCharDelayMs')" class="mt-2 text-xs text-rose-600">{{ getFieldError('perCharDelayMs') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'template_assert'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">模板选择</label>
          <el-select v-model="step.templateId" class="!w-full" clearable>
            <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
          </el-select>
          <p v-if="getFieldError('templateId')" class="mt-2 text-xs text-rose-600">{{ getFieldError('templateId') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">阈值</label>
          <el-input-number v-model="step.threshold" :max="1" :min="0" :precision="2" :step="0.01" :value-on-clear="null" class="!w-full" />
          <p v-if="getFieldError('threshold')" class="mt-2 text-xs text-rose-600">{{ getFieldError('threshold') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'ocr_assert'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">OCR 模板(可选)</label>
          <el-select v-model="step.templateId" class="!w-full" clearable>
            <el-option v-for="option in getStepTemplateOptionsFn(step)" :key="option.id" :label="option.label" :value="option.id" />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">选择器</label>
          <el-input v-model="step.selector" />
          <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">{{ getFieldError('selector') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">期望文本</label>
          <el-input v-model="step.expectedText" />
          <p v-if="getFieldError('expectedText')" class="mt-2 text-xs text-rose-600">{{ getFieldError('expectedText') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">匹配模式</label>
          <el-select v-model="step.matchMode" class="!w-full">
            <el-option v-for="option in OCR_MATCH_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('matchMode')" class="mt-2 text-xs text-rose-600">{{ getFieldError('matchMode') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'navigate'">
        <div class="col-span-2">
          <label class="mb-2 block text-xs font-medium text-slate-700">URL / 相对路径</label>
          <el-input v-model="step.url" />
          <p v-if="getFieldError('url')" class="mt-2 text-xs text-rose-600">{{ getFieldError('url') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">等待策略</label>
          <el-select v-model="step.waitUntil" class="!w-full">
            <el-option v-for="option in NAVIGATE_WAIT_UNTIL_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('waitUntil')" class="mt-2 text-xs text-rose-600">{{ getFieldError('waitUntil') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'scroll'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">滑动目标</label>
          <el-select v-model="step.scrollTarget" class="!w-full">
            <el-option v-for="option in SCROLL_TARGET_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('scrollTarget')" class="mt-2 text-xs text-rose-600">{{ getFieldError('scrollTarget') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">滑动方向</label>
          <el-select v-model="step.direction" class="!w-full">
            <el-option v-for="option in SCROLL_DIRECTION_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('direction')" class="mt-2 text-xs text-rose-600">{{ getFieldError('direction') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">滑动距离(px)</label>
          <el-input-number v-model="step.distance" :min="1" class="!w-full" />
          <p v-if="getFieldError('distance')" class="mt-2 text-xs text-rose-600">{{ getFieldError('distance') }}</p>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">滑动行为</label>
          <el-select v-model="step.behavior" class="!w-full">
            <el-option v-for="option in SCROLL_BEHAVIOR_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('behavior')" class="mt-2 text-xs text-rose-600">{{ getFieldError('behavior') }}</p>
        </div>
      </template>

      <template v-if="step.type === 'long_press'">
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">定位方式</label>
          <el-select v-model="step.locator" class="!w-full">
            <el-option v-for="option in LOCATOR_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-xs font-medium text-slate-700">长按时长(ms)</label>
          <el-input-number v-model="step.durationMs" :min="1" class="!w-full" />
          <p v-if="getFieldError('durationMs')" class="mt-2 text-xs text-rose-600">{{ getFieldError('durationMs') }}</p>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-xs font-medium text-slate-700">选择器</label>
          <el-input v-model="step.selector" />
          <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">{{ getFieldError('selector') }}</p>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-xs font-medium text-slate-700">按钮类型</label>
          <el-select v-model="step.button" class="!w-full">
            <el-option v-for="option in LONG_PRESS_BUTTON_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <p v-if="getFieldError('button')" class="mt-2 text-xs text-rose-600">{{ getFieldError('button') }}</p>
        </div>
      </template>

      <div>
        <label class="mb-2 block text-xs font-medium text-slate-700">超时(ms)</label>
        <el-input-number v-model="step.timeoutMs" :min="1" class="!w-full" />
        <p v-if="getFieldError('timeoutMs')" class="mt-2 text-xs text-rose-600">{{ getFieldError('timeoutMs') }}</p>
      </div>
      <div>
        <label class="mb-2 block text-xs font-medium text-slate-700">重试次数</label>
        <el-input-number v-model="step.retryTimes" :min="0" class="!w-full" />
        <p v-if="getFieldError('retryTimes')" class="mt-2 text-xs text-rose-600">{{ getFieldError('retryTimes') }}</p>
      </div>
      <div class="col-span-2">
        <label class="mb-2 block text-xs font-medium text-slate-700">高级 payload</label>
        <el-input v-model="step.extraPayloadJson" :rows="4" type="textarea" />
        <p v-if="getFieldError('extraPayloadJson')" class="mt-2 text-xs text-rose-600">{{ getFieldError('extraPayloadJson') }}</p>
      </div>
    </div>
  </div>
</template>
