<script setup lang="ts">
import { CircleCheck, Loading, WarningFilled } from '@element-plus/icons-vue'

import type { StepCanvasValidationError } from '@/types/stepCanvas'
import type { EditableStepPath } from '@/types/stepGraph'

withDefaults(
  defineProps<{
    stepCount: number
    branchCount: number
    componentCount: number
    selectedCount?: number
    errorCount?: number
    zoomPercent?: number
    message?: string
    loadingPreferences?: boolean
    errors?: StepCanvasValidationError[]
  }>(),
  {
    selectedCount: 0,
    errorCount: 0,
    zoomPercent: 100,
    message: '',
    loadingPreferences: false,
    errors: () => []
  }
)

const emit = defineEmits<{
  (event: 'show-errors'): void
  (event: 'locate-error', path: EditableStepPath): void
}>()
</script>

<template>
  <footer class="step-canvas-status-bar" aria-label="步骤画布状态">
    <div class="status-section status-metrics" aria-label="画布指标">
      <span class="status-metric status-step-count">
        <span class="status-label-full">{{ stepCount }} 个步骤</span>
        <span class="status-label-compact" aria-hidden="true">{{ stepCount }} 步</span>
      </span>
      <span class="status-metric status-branch-count">{{ branchCount }} 个分支</span>
      <span class="status-metric status-component-count">
        {{ componentCount }} 个组件引用
      </span>
      <span v-if="selectedCount > 0" class="status-metric status-selected-count">
        {{ selectedCount }} 个已选择
      </span>
    </div>

    <div class="status-section status-primary">
      <span
        v-if="loadingPreferences"
        class="status-loading"
        aria-label="正在恢复画布偏好"
      >
        <el-icon class="is-loading"><Loading /></el-icon>
        <span class="status-label-full">恢复画布偏好</span>
        <span class="status-label-compact" aria-hidden="true">恢复中</span>
      </span>
      <el-popover
        v-else-if="message"
        placement="top-end"
        trigger="click"
        :width="320"
      >
        <template #reference>
          <button
            class="status-message-button"
            type="button"
            :aria-label="`画布状态：${message}`"
            :title="message"
          >
            <span class="status-message-full" aria-hidden="true">{{ message }}</span>
            <span class="status-label-compact" aria-hidden="true">状态</span>
          </button>
        </template>
        <p class="status-message-detail">{{ message }}</p>
      </el-popover>
      <el-popover
        v-if="errorCount > 0"
        placement="top-end"
        trigger="click"
        :width="320"
      >
        <template #reference>
          <button
            class="status-error-button"
            type="button"
            :aria-label="`${errorCount} 个配置错误`"
            @click="emit('show-errors')"
          >
            <el-icon><WarningFilled /></el-icon>
            <span class="status-label-full">{{ errorCount }} 个配置错误</span>
            <span class="status-label-compact" aria-hidden="true">
              {{ errorCount }} 错误
            </span>
          </button>
        </template>
        <div class="status-error-list">
          <strong class="status-error-title">配置错误</strong>
          <button
            v-for="error in errors"
            :key="error.path"
            class="status-error-item"
            type="button"
            @click="emit('locate-error', error.path)"
          >
            <span>{{ error.nodeLabel }}</span>
            <small>{{ error.messages.join(' ') }}</small>
          </button>
          <span v-if="errors.length === 0" class="status-error-empty">
            请检查当前步骤配置。
          </span>
        </div>
      </el-popover>
      <span v-else class="status-success">
        <el-icon><CircleCheck /></el-icon>
        无配置错误
      </span>
      <span class="status-zoom">{{ zoomPercent }}%</span>
      <span
        v-if="message"
        class="status-visually-hidden"
        aria-live="polite"
        role="status"
      >
        {{ message }}
      </span>
    </div>
  </footer>
</template>

<style scoped>
.step-canvas-status-bar {
  display: flex;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  height: 32px;
  padding: 0 8px;
  overflow: hidden;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  background: #fff;
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}

.status-section {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.status-metrics {
  flex: 0 0 auto;
}

.status-primary {
  flex: 1 1 auto;
  justify-content: flex-end;
  margin-left: auto;
}

.status-metric,
.status-error-button,
.status-loading,
.status-success,
.status-zoom {
  flex: 0 0 auto;
}

.status-branch-count,
.status-component-count,
.status-selected-count,
.status-success,
.status-zoom,
.status-label-full,
.status-message-full {
  display: none;
}

.status-label-compact {
  display: inline;
}

.status-loading,
.status-success {
  align-items: center;
  gap: 4px;
}

.status-loading {
  display: inline-flex;
  color: #64748b;
}

.status-message-button {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  padding: 2px 3px;
  border: 0;
  color: #64748b;
  background: transparent;
  font: inherit;
  line-height: 1;
  cursor: pointer;
}

.status-message-full {
  min-width: 0;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-message-detail {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.status-error-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 3px;
  border: 0;
  color: #be123c;
  background: transparent;
  font: inherit;
  line-height: 1;
  cursor: pointer;
}

.status-message-button:hover,
.status-message-button:focus-visible,
.status-error-button:hover,
.status-error-button:focus-visible {
  text-decoration: underline;
  outline: 2px solid #1d4ed8;
  outline-offset: -1px;
}

.status-message-button:hover,
.status-message-button:focus-visible {
  color: #334155;
}

.status-error-button:hover,
.status-error-button:focus-visible {
  color: #9f1239;
}

.status-error-list {
  display: flex;
  max-height: 320px;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.status-error-title {
  color: #1e293b;
  font-size: 13px;
}

.status-error-item {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 3px;
  padding: 8px;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  color: #9f1239;
  background: #fff1f2;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.status-error-item:hover,
.status-error-item:focus-visible {
  border-color: #e11d48;
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.status-error-item span {
  font-weight: 600;
}

.status-error-item small,
.status-error-empty {
  color: #64748b;
  font-size: 11px;
  line-height: 16px;
}

.status-success {
  color: #047857;
}

.status-visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
  white-space: nowrap;
}

@media (min-width: 640px) {
  .status-label-full,
  .status-message-full,
  .status-branch-count,
  .status-success {
    display: inline;
  }

  .status-success {
    display: inline-flex;
  }

  .status-label-compact {
    display: none;
  }

  .status-message-full {
    max-width: 240px;
  }
}

@media (min-width: 768px) {
  .status-component-count {
    display: inline;
  }

  .status-message-full {
    max-width: 320px;
  }
}

@media (min-width: 960px) {
  .step-canvas-status-bar {
    height: 28px;
    padding: 0 10px;
  }

  .status-section {
    gap: 14px;
  }

  .status-selected-count,
  .status-zoom {
    display: inline;
  }
}
</style>
