<script setup lang="ts">
import type {
  StepGraphConnectionStyle,
  StepGraphEdgeKind
} from '@/types/stepGraph'
import { getStepGraphEdgeVisual } from '@/utils/stepGraph'

interface LegendEntry {
  kind: StepGraphEdgeKind
  label: string
}

defineProps<{
  connectionStyle: StepGraphConnectionStyle
  showEdgeLabels: boolean
}>()

const emit = defineEmits<{
  (event: 'update:connectionStyle', value: StepGraphConnectionStyle): void
}>()

const geometryOptions: Array<{
  value: StepGraphConnectionStyle
  label: string
}> = [
  { value: 'straight', label: '直线' },
  { value: 'step', label: '折线' },
  { value: 'bezier', label: '曲线' }
]

const legendEntries: LegendEntry[] = [
  { kind: 'sequence', label: '顺序' },
  { kind: 'condition', label: '条件' },
  { kind: 'else', label: 'Else' },
  { kind: 'component', label: '组件引用' },
  { kind: 'dependency-annotation', label: '依赖 · 仅标注' },
  { kind: 'parallel-annotation', label: '并行 · 仅标注' }
]
</script>

<template>
  <aside class="step-canvas-legend" aria-label="连接线图例">
    <div class="connection-style-switch" aria-label="连接样式">
      <button
        v-for="option in geometryOptions"
        :key="option.value"
        :aria-pressed="connectionStyle === option.value"
        :class="{ 'is-active': connectionStyle === option.value }"
        type="button"
        @click="emit('update:connectionStyle', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="legend-items">
      <span
        v-for="entry in legendEntries"
        :key="entry.kind"
        class="legend-item"
      >
        <i
          aria-hidden="true"
          class="legend-line"
          :class="{
            'is-double': getStepGraphEdgeVisual(entry.kind).doubleTrack,
            'is-solid': getStepGraphEdgeVisual(entry.kind).dasharray === null,
            'is-dotted': entry.kind === 'component'
          }"
          :style="{
            '--legend-color': getStepGraphEdgeVisual(entry.kind).color
          }"
        />
        {{ entry.label }}
      </span>
    </div>
    <small v-if="!showEdgeLabels">缩放低于 60%，边标签已隐藏</small>
  </aside>
</template>

<style scoped>
.step-canvas-legend {
  position: absolute;
  z-index: 5;
  top: 10px;
  left: 10px;
  display: flex;
  max-width: min(720px, calc(100% - 20px));
  align-items: center;
  gap: 10px;
  padding: 5px 7px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: #475569;
  background: rgb(255 255 255 / 94%);
  box-shadow: 0 2px 8px rgb(15 23 42 / 8%);
  font-size: 10px;
}

.connection-style-switch {
  display: flex;
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 5px;
}

.connection-style-switch button {
  height: 24px;
  padding: 0 7px;
  border: 0;
  border-right: 1px solid #cbd5e1;
  color: #475569;
  background: #fff;
  font: inherit;
  cursor: pointer;
}

.connection-style-switch button:last-child {
  border-right: 0;
}

.connection-style-switch button:hover,
.connection-style-switch button:focus-visible,
.connection-style-switch button.is-active {
  color: #1d4ed8;
  background: #eff6ff;
}

.connection-style-switch button:focus-visible {
  outline: 2px solid #1d4ed8;
  outline-offset: -2px;
}

.connection-style-switch button.is-active {
  font-weight: 700;
}

.legend-items {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  overflow-x: auto;
  white-space: nowrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.legend-line {
  position: relative;
  display: inline-block;
  width: 22px;
  height: 0;
  border-top: 2px solid var(--legend-color);
  border-image: none;
}

.legend-line:not(.is-double) {
  border-top-style: dashed;
}

.legend-line.is-solid {
  border-top-style: solid;
}

.legend-line.is-dotted {
  border-top-style: dotted;
}

.legend-line.is-double::before,
.legend-line.is-double::after {
  position: absolute;
  right: 0;
  left: 0;
  border-top: 1px dashed var(--legend-color);
  content: '';
}

.legend-line.is-double::before {
  top: -3px;
}

.legend-line.is-double::after {
  top: 1px;
}

.step-canvas-legend small {
  flex: 0 0 auto;
  color: #b45309;
  white-space: nowrap;
}

@media (max-width: 959px) {
  .step-canvas-legend {
    right: 8px;
    left: 8px;
    align-items: flex-start;
    flex-direction: column;
  }

  .legend-items {
    width: 100%;
  }
}
</style>
