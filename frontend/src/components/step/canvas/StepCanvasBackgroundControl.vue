<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  useId
} from 'vue'
import { Delete, Picture, Upload } from '@element-plus/icons-vue'
import type { ButtonInstance } from 'element-plus'

import type { StepCanvasBackgroundPatch } from '@/composables/useStepCanvasPreferences'
import type { StepGraphBackgroundKind, StepGraphBackgroundPreference } from '@/types/stepGraph'

const props = withDefaults(
  defineProps<{
    preference: StepGraphBackgroundPreference
    hasImage?: boolean
    busy?: boolean
    compact?: boolean
  }>(),
  {
    hasImage: false,
    busy: false,
    compact: false
  }
)

const emit = defineEmits<{
  (event: 'patch', patch: StepCanvasBackgroundPatch): void
  (event: 'select-image', file: File): void
  (event: 'remove-image'): void
}>()

const controlRef = ref<HTMLDivElement | null>(null)
const panelVisible = ref(false)
const triggerButtonRef = ref<ButtonInstance | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
const panelId = `step-canvas-background-${useId()}`
const panelTitleId = `${panelId}-title`

const opacityPercent = computed((): number =>
  Math.round((props.preference.imageOpacity ?? 0.65) * 100)
)

function updateKind(value: string | number | boolean): void {
  emit('patch', { kind: value as StepGraphBackgroundKind })
}

function updateColor(value: string | null): void {
  if (value) {
    emit('patch', { color: value })
  }
}

function updateImageFit(value: string | number | boolean): void {
  emit('patch', {
    imageFit: value as NonNullable<StepGraphBackgroundPreference['imageFit']>
  })
}

function updateOpacity(value: number): void {
  emit('patch', { imageOpacity: value / 100 })
}

function updateImageFixed(value: string | number | boolean): void {
  emit('patch', { imageFixed: Boolean(value) })
}

function focusTrigger(): void {
  void nextTick((): void => {
    triggerButtonRef.value?.ref?.focus()
  })
}

function closePanel(restoreFocus = true): void {
  if (!panelVisible.value) {
    return
  }
  panelVisible.value = false
  if (restoreFocus) {
    focusTrigger()
  }
}

function openPanel(): void {
  if (props.busy || panelVisible.value) {
    return
  }
  panelVisible.value = true
  void nextTick((): void => {
    panelRef.value?.focus()
  })
}

function togglePanel(): void {
  if (panelVisible.value) {
    closePanel()
  } else {
    openPanel()
  }
}

function handleTriggerKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  togglePanel()
}

function handleDocumentPointerDown(event: Event): void {
  if (
    panelVisible.value &&
    event.target instanceof Node &&
    !controlRef.value?.contains(event.target)
  ) {
    closePanel()
  }
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (!panelVisible.value || event.key !== 'Escape') {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  closePanel()
}

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    emit('select-image', file)
  }
  input.value = ''
}

onMounted((): void => {
  document.addEventListener('pointerdown', handleDocumentPointerDown)
  document.addEventListener('keydown', handleDocumentKeydown)
})

onBeforeUnmount((): void => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
  document.removeEventListener('keydown', handleDocumentKeydown)
})
</script>

<template>
  <div
    ref="controlRef"
    class="step-canvas-background-anchor"
    :class="{ 'is-compact': compact }"
  >
    <el-button
      ref="triggerButtonRef"
      :aria-controls="panelId"
      :aria-expanded="String(panelVisible)"
      aria-haspopup="dialog"
      aria-label="配置画布背景"
      :disabled="busy"
      :loading="busy"
      plain
      title="画布背景"
      @click="togglePanel"
      @keydown="handleTriggerKeydown"
    >
      <el-icon v-if="!busy"><Picture /></el-icon>
      <span v-if="!compact" class="ml-1">背景</span>
    </el-button>

    <div
      v-if="panelVisible"
      :id="panelId"
      ref="panelRef"
      class="step-canvas-background-control"
      role="dialog"
      :aria-labelledby="panelTitleId"
      style="opacity: 1; visibility: visible"
      tabindex="-1"
    >
      <h2 :id="panelTitleId" class="step-canvas-background-title">
        画布背景设置
      </h2>

      <el-radio-group
        :model-value="preference.kind"
        class="!flex"
        size="small"
        @update:model-value="updateKind"
      >
        <el-radio-button value="grid">网格</el-radio-button>
        <el-radio-button value="solid">纯色</el-radio-button>
        <el-radio-button value="image">图片</el-radio-button>
      </el-radio-group>

      <div v-if="preference.kind === 'solid'" class="mt-4 flex items-center justify-between">
        <span class="text-sm text-slate-600">背景颜色</span>
        <el-color-picker
          :model-value="preference.color ?? '#f8fafc'"
          @change="updateColor"
        />
      </div>

      <div v-if="preference.kind === 'image'" class="mt-4 space-y-4">
        <div class="flex gap-2">
          <label
            class="step-canvas-upload-control"
            :class="{ 'is-disabled': busy }"
          >
            <el-icon aria-hidden="true"><Upload /></el-icon>
            <span>{{ hasImage ? '替换图片' : '上传图片' }}</span>
            <input
              accept="image/png,image/jpeg,image/webp"
              aria-label="上传画布背景图片"
              :disabled="busy"
              type="file"
              @change="handleFileChange"
            />
          </label>
          <el-button
            v-if="hasImage"
            :icon="Delete"
            :disabled="busy"
            plain
            type="danger"
            @click="emit('remove-image')"
          >
            移除
          </el-button>
        </div>
        <p class="m-0 text-xs leading-5 text-slate-500">
          支持 PNG、JPEG、WebP，文件不超过 5 MB。图片仅保存在当前浏览器。
        </p>

        <div>
          <label class="mb-2 block text-sm text-slate-600">填充方式</label>
          <el-select
            :model-value="preference.imageFit ?? 'cover'"
            class="!w-full"
            @update:model-value="updateImageFit"
          >
            <el-option label="覆盖画布" value="cover" />
            <el-option label="完整显示" value="contain" />
            <el-option label="平铺" value="repeat" />
          </el-select>
        </div>

        <div>
          <div class="mb-1 flex items-center justify-between text-sm text-slate-600">
            <span>透明度</span>
            <span>{{ opacityPercent }}%</span>
          </div>
          <el-slider
            :model-value="opacityPercent"
            :min="10"
            :max="100"
            @update:model-value="updateOpacity"
          />
        </div>

        <div class="flex items-center justify-between">
          <span class="text-sm text-slate-600">固定在视口</span>
          <el-switch
            :model-value="preference.imageFixed ?? true"
            @update:model-value="updateImageFixed"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-canvas-background-anchor {
  position: relative;
  z-index: 20;
  display: inline-flex;
  flex: 0 0 auto;
}

.step-canvas-background-control {
  position: absolute;
  z-index: 3200;
  top: calc(100% + 8px);
  right: 0;
  box-sizing: border-box;
  width: 300px;
  max-width: calc(100vw - 16px);
  max-height: calc(100vh - 76px);
  padding: 16px;
  overflow: auto;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  opacity: 1;
  visibility: visible;
  background: #fff;
  box-shadow: 0 8px 24px rgb(15 23 42 / 16%);
}

.step-canvas-background-control:focus {
  outline: none;
}

.step-canvas-background-title {
  margin: 0 0 14px;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
  line-height: 20px;
}

.step-canvas-background-control :deep(.el-radio-button__inner) {
  border-radius: 0;
}

.step-canvas-background-control :deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-radius: 6px 0 0 6px;
}

.step-canvas-background-control :deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 0 6px 6px 0;
}

.step-canvas-upload-control {
  position: relative;
  box-sizing: border-box;
  display: inline-flex;
  height: 32px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 15px;
  overflow: hidden;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  color: #606266;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.step-canvas-upload-control:hover {
  border-color: #c6e2ff;
  color: #409eff;
  background: #ecf5ff;
}

.step-canvas-upload-control:focus-within {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.step-canvas-upload-control.is-disabled {
  color: #a8abb2;
  background: #fff;
  cursor: not-allowed;
}

.step-canvas-upload-control input {
  position: absolute;
  width: 100%;
  height: 100%;
  inset: 0;
  opacity: 0;
  cursor: inherit;
}

@media (max-width: 959px) {
  .step-canvas-background-anchor.is-compact .step-canvas-background-control {
    width: min(300px, calc(100vw - 16px));
    max-height: calc(100vh - 72px);
  }
}
</style>
