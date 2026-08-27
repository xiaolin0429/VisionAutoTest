<script setup lang="ts">
import { Connection, EditPen, Setting } from '@element-plus/icons-vue'

import type { StepGraphNode } from '@/types/stepGraph'

export type StepCanvasInspectorTab = 'config' | 'style' | 'relation'

withDefaults(
  defineProps<{
    selectedNode?: StepGraphNode | null
    activeTab?: StepCanvasInspectorTab
    collapsed?: boolean
  }>(),
  {
    selectedNode: null,
    activeTab: 'config',
    collapsed: false
  }
)

const emit = defineEmits<{
  (event: 'update:activeTab', value: StepCanvasInspectorTab): void
  (event: 'request-expand'): void
}>()

function updateActiveTab(value: string | number): void {
  emit('update:activeTab', value as StepCanvasInspectorTab)
}
</script>

<template>
  <aside class="step-canvas-inspector" :class="{ 'is-collapsed': collapsed }">
    <template v-if="collapsed">
      <el-tooltip content="配置" placement="left">
        <button
          aria-label="展开配置检查器"
          class="inspector-rail-button"
          type="button"
          @click="emit('request-expand')"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </el-tooltip>
    </template>

    <template v-else>
      <el-tabs
        :model-value="activeTab"
        class="inspector-tabs"
        stretch
        @update:model-value="updateActiveTab"
      >
        <el-tab-pane name="config">
          <template #label>
            <span class="flex items-center gap-1">
              <el-icon><Setting /></el-icon>
              配置
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="style">
          <template #label>
            <span class="flex items-center gap-1">
              <el-icon><EditPen /></el-icon>
              样式
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="relation">
          <template #label>
            <span class="flex items-center gap-1">
              <el-icon><Connection /></el-icon>
              关系
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <div class="inspector-content">
        <slot
          :node="selectedNode"
          :active-tab="activeTab"
        >
          <div v-if="selectedNode" class="inspector-placeholder">
            <p class="m-0 text-sm font-semibold text-slate-800">
              {{ selectedNode.label }}
            </p>
            <p class="mb-0 mt-2 text-xs leading-5 text-slate-500">
              {{ selectedNode.detail }}
            </p>
            <p class="mb-0 mt-4 text-xs leading-5 text-slate-400">
              {{ activeTab === 'config'
                ? '步骤配置将在后续任务接入共享字段。'
                : activeTab === 'style'
                  ? '节点样式将在后续任务接入。'
                  : '说明性关系将在后续任务接入。' }}
            </p>
          </div>
          <div v-else class="inspector-empty">
            在画布或大纲中选择节点以查看配置。
          </div>
        </slot>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.step-canvas-inspector {
  display: flex;
  min-width: 0;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border-left: 1px solid #e2e8f0;
  background: #fff;
}

.step-canvas-inspector.is-collapsed {
  align-items: center;
  padding: 8px 4px;
}

.inspector-rail-button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #475569;
  background: transparent;
  cursor: pointer;
}

.inspector-rail-button:hover,
.inspector-rail-button:focus-visible {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
}

.inspector-rail-button:focus-visible {
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 20%);
}

.inspector-tabs {
  padding: 4px 10px 0;
}

.inspector-content {
  min-height: 0;
  flex: 1;
  padding: 12px;
  overflow: auto;
}

.inspector-placeholder {
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.inspector-empty {
  padding: 28px 12px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

.step-canvas-inspector :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.step-canvas-inspector :deep(.el-tabs__item:focus-visible) {
  outline: 2px solid #1d4ed8;
  outline-offset: -2px;
  box-shadow: inset 0 0 0 2px rgb(37 99 235 / 18%);
}
</style>
