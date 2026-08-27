<script setup lang="ts">
import OcrTargetFields from './OcrTargetFields.vue'
import {
  INPUT_MODE_OPTIONS,
  LONG_PRESS_BUTTON_OPTIONS,
  LOCATOR_TYPE_OPTIONS,
  NAVIGATE_WAIT_UNTIL_OPTIONS,
  OCR_ASSERTION_MODE_OPTIONS,
  OCR_ASSERTION_SCOPE_OPTIONS,
  SCROLL_BEHAVIOR_OPTIONS,
  SCROLL_DIRECTION_OPTIONS,
  SCROLL_TARGET_OPTIONS,
  supportsOcrLocator,
  type StepDraft,
  type StepFieldErrorGetter,
  type StepTemplateOption
} from '@/utils/steps'
import type { Component } from '@/types/models'

const props = withDefaults(
  defineProps<{
    step: StepDraft
    components?: Component[]
    allowComponentCall?: boolean
    getFieldError: StepFieldErrorGetter
    getStepTemplateOptionsFn: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
    formatComponentOptionLabelFn?: (component: Component) => string
  }>(),
  {
    components: () => [],
    allowComponentCall: false,
    getStepTemplateHintFn: undefined,
    formatComponentOptionLabelFn: undefined
  }
)

function showLocatorFields(step: StepDraft): boolean {
  if (!supportsOcrLocator(step.type)) {
    return false
  }

  return step.type !== 'scroll' || step.scrollTarget === 'element'
}

function getTemplateHint(step: StepDraft): string {
  return props.getStepTemplateHintFn?.(step) ?? ''
}

function formatComponentLabel(component: Component): string {
  if (props.formatComponentOptionLabelFn) {
    return props.formatComponentOptionLabelFn(component)
  }
  return `${component.name} (#${component.id}) · ${component.status}`
}
</script>

<template>
  <!-- wait -->
  <template v-if="step.type === 'wait'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">等待时长(ms)</label>
      <el-input-number v-model="step.waitMs" :min="0" class="!w-full" />
      <p v-if="getFieldError('waitMs')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('waitMs') }}
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
      <p v-if="getFieldError('url')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('url') }}
      </p>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">等待策略</label>
      <el-select v-model="step.waitUntil" class="!w-full">
        <el-option
          v-for="option in NAVIGATE_WAIT_UNTIL_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('waitUntil')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('waitUntil') }}
      </p>
    </div>
  </template>

  <!-- scroll -->
  <template v-if="step.type === 'scroll'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">滑动目标</label>
      <el-select v-model="step.scrollTarget" class="!w-full">
        <el-option
          v-for="option in SCROLL_TARGET_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('scrollTarget')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('scrollTarget') }}
      </p>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">滑动方向</label>
      <el-select v-model="step.direction" class="!w-full">
        <el-option
          v-for="option in SCROLL_DIRECTION_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('direction')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('direction') }}
      </p>
    </div>
  </template>

  <!-- locator mode -->
  <template v-if="showLocatorFields(step)">
    <div :class="{ 'col-span-2': step.type === 'scroll' }">
      <label class="mb-2 block text-sm font-medium text-slate-700">定位方式</label>
      <el-select v-model="step.locator" class="!w-full">
        <el-option
          v-for="option in LOCATOR_TYPE_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
    </div>
    <div v-if="step.type === 'input'">
      <label class="mb-2 block text-sm font-medium text-slate-700">输入方式</label>
      <el-select v-model="step.inputMode" class="!w-full">
        <el-option
          v-for="option in INPUT_MODE_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('inputMode')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('inputMode') }}
      </p>
    </div>
    <div v-if="step.type === 'long_press'">
      <label class="mb-2 block text-sm font-medium text-slate-700">长按时长(ms)</label>
      <el-input-number v-model="step.durationMs" :min="1" class="!w-full" />
      <p v-if="getFieldError('durationMs')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('durationMs') }}
      </p>
    </div>

    <div v-if="step.type === 'input'" class="col-span-2">
      <label class="mb-2 block text-sm font-medium text-slate-700">输入文本</label>
      <el-input v-model="step.text" placeholder="请输入要填充的内容" />
      <p v-if="getFieldError('text')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('text') }}
      </p>
    </div>

    <div v-if="step.locator !== 'ocr'" class="col-span-2">
      <template v-if="step.locator === 'selector'">
        <label class="mb-2 block text-sm font-medium text-slate-700">
          {{ step.type === 'scroll' ? '目标元素选择器' : '选择器' }}
        </label>
        <el-input
          v-model="step.selector"
          :placeholder="step.type === 'scroll' ? '例如 .table-container' : `例如 [data-testid='target']`"
        />
        <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('selector') }}
        </p>
      </template>
      <template v-else-if="step.locator === 'visual'">
        <label class="mb-2 block text-sm font-medium text-slate-700">视觉模板</label>
        <el-select
          v-model="step.visualTemplateId"
          class="!w-full"
          clearable
          placeholder="请选择 template 策略模板"
        >
          <el-option
            v-for="option in getStepTemplateOptionsFn(step)"
            :key="option.id"
            :label="option.label"
            :value="option.id"
          />
        </el-select>
        <p v-if="getFieldError('visualTemplateId')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('visualTemplateId') }}
        </p>
        <p v-else-if="getTemplateHint(step)" class="mt-2 text-xs text-amber-600">
          {{ getTemplateHint(step) }}
        </p>
      </template>
    </div>

    <OcrTargetFields
      v-if="step.locator === 'ocr'"
      :target="step.ocrTarget"
      :title="step.type === 'scroll' ? '滑动目标' : '交互目标'"
    />

    <template v-if="step.locator === 'visual'">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">匹配阈值(可选)</label>
        <el-input-number
          v-model="step.visualThreshold"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.01"
          :value-on-clear="null"
          class="!w-full"
          placeholder="留空则使用模板默认阈值"
        />
        <p v-if="getFieldError('visualThreshold')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('visualThreshold') }}
        </p>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">锚点横向比例</label>
        <el-input-number
          v-model="step.visualAnchorXRatio"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.01"
          class="!w-full"
        />
        <p v-if="getFieldError('visualAnchorXRatio')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('visualAnchorXRatio') }}
        </p>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">锚点纵向比例</label>
        <el-input-number
          v-model="step.visualAnchorYRatio"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.01"
          class="!w-full"
        />
        <p v-if="getFieldError('visualAnchorYRatio')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('visualAnchorYRatio') }}
        </p>
      </div>
    </template>
  </template>

  <!-- OCR select -->
  <template v-if="step.type === 'select_option'">
    <OcrTargetFields :target="step.fieldTarget" title="字段目标" />
    <OcrTargetFields :target="step.optionTarget" title="选项目标" />
    <div class="col-span-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
      <el-checkbox v-model="step.verifySelected">选择后重新 OCR 验证结果</el-checkbox>
    </div>
  </template>

  <!-- input -->
  <template v-if="step.type === 'input'">
    <div v-if="step.inputMode === 'otp'">
      <label class="mb-2 block text-sm font-medium text-slate-700">验证码长度</label>
      <el-input-number v-model="step.otpLength" :min="1" class="!w-full" />
      <p v-if="getFieldError('otpLength')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('otpLength') }}
      </p>
    </div>
    <div v-if="step.inputMode !== 'fill'">
      <label class="mb-2 block text-sm font-medium text-slate-700">逐字符延迟(ms)</label>
      <el-input-number v-model="step.perCharDelayMs" :min="0" class="!w-full" />
      <p v-if="getFieldError('perCharDelayMs')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('perCharDelayMs') }}
      </p>
    </div>
  </template>

  <!-- scroll runtime -->
  <template v-if="step.type === 'scroll'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">滑动距离(px)</label>
      <el-input-number v-model="step.distance" :min="1" class="!w-full" />
      <p v-if="getFieldError('distance')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('distance') }}
      </p>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">滑动行为</label>
      <el-select v-model="step.behavior" class="!w-full">
        <el-option
          v-for="option in SCROLL_BEHAVIOR_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('behavior')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('behavior') }}
      </p>
    </div>
  </template>

  <!-- long press -->
  <template v-if="step.type === 'long_press'">
    <div class="col-span-2">
      <label class="mb-2 block text-sm font-medium text-slate-700">按钮类型</label>
      <el-select v-model="step.button" class="!w-full">
        <el-option
          v-for="option in LONG_PRESS_BUTTON_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p class="mt-2 text-xs text-slate-500">
        首期固定支持 `left`，用于覆盖常见 Web UI 与 H5 长按场景。
      </p>
      <p v-if="getFieldError('button')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('button') }}
      </p>
    </div>
  </template>

  <!-- template assert -->
  <template v-if="step.type === 'template_assert'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">模板选择</label>
      <el-select
        v-model="step.templateId"
        class="!w-full"
        clearable
        placeholder="请选择 template 策略模板"
      >
        <el-option
          v-for="option in getStepTemplateOptionsFn(step)"
          :key="option.id"
          :label="option.label"
          :value="option.id"
        />
      </el-select>
      <p v-if="getFieldError('templateId')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('templateId') }}
      </p>
      <p v-else-if="getTemplateHint(step)" class="mt-2 text-xs text-amber-600">
        {{ getTemplateHint(step) }}
      </p>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">阈值(可选)</label>
      <el-input-number
        v-model="step.threshold"
        :max="1"
        :min="0"
        :precision="2"
        :step="0.01"
        :value-on-clear="null"
        class="!w-full"
        placeholder="留空则使用模板默认阈值"
      />
      <p v-if="getFieldError('threshold')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('threshold') }}
      </p>
    </div>
  </template>

  <!-- OCR assert -->
  <template v-if="step.type === 'ocr_assert'">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">断言范围</label>
      <el-select
        v-model="step.ocrAssertionScope"
        class="!w-full"
      >
        <el-option
          v-for="option in OCR_ASSERTION_SCOPE_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('ocrAssertionScope')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('ocrAssertionScope') }}
      </p>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-700">断言模式</label>
      <el-select v-model="step.ocrAssertionMode" class="!w-full">
        <el-option
          v-for="option in OCR_ASSERTION_MODE_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <p v-if="getFieldError('ocrAssertionMode')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('ocrAssertionMode') }}
      </p>
    </div>

    <div
      v-if="step.ocrAssertionScope === 'element_legacy'"
      class="col-span-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
    >
      兼容模式：仅对 selector 元素区域截图。新建断言应使用当前视口或整页范围。
    </div>

    <template v-if="step.ocrAssertionScope === 'element_legacy'">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">兼容选择器</label>
        <el-input v-model="step.selector" placeholder="例如 [data-testid='result-banner']" />
        <p v-if="getFieldError('selector')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('selector') }}
        </p>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">旧 OCR 模板(可选)</label>
        <el-select
          v-model="step.templateId"
          class="!w-full"
          clearable
          placeholder="仅保留历史资产关联"
        >
          <el-option
            v-for="option in getStepTemplateOptionsFn(step)"
            :key="option.id"
            :label="option.label"
            :value="option.id"
          />
        </el-select>
        <p v-if="getTemplateHint(step)" class="mt-2 text-xs text-amber-600">
          {{ getTemplateHint(step) }}
        </p>
      </div>
    </template>

    <div v-if="step.ocrAssertionMode === 'count'" class="col-span-2">
      <label class="mb-2 block text-sm font-medium text-slate-700">期望数量</label>
      <el-input-number v-model="step.ocrExpectedCount" :min="0" class="!w-full" />
      <p v-if="getFieldError('ocrExpectedCount')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('ocrExpectedCount') }}
      </p>
    </div>

    <OcrTargetFields
      :target="step.ocrTarget"
      title="断言目标"
      :show-scope="false"
      :show-action-point="false"
    />
  </template>

  <!-- component call -->
  <template v-if="step.type === 'component_call' && allowComponentCall">
    <div class="col-span-2">
      <label class="mb-2 block text-sm font-medium text-slate-700">组件选择</label>
      <el-select v-model="step.componentId" class="!w-full" clearable placeholder="请选择组件">
        <el-option
          v-for="item in components"
          :key="item.id"
          :label="formatComponentLabel(item)"
          :value="item.id"
        />
      </el-select>
      <p v-if="getFieldError('componentId')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('componentId') }}
      </p>
    </div>
  </template>
</template>
