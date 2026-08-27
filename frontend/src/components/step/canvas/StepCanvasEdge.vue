<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  getStraightPath,
  type EdgeProps
} from '@vue-flow/core'

import type { StepCanvasEdgeData } from '@/types/stepCanvas'

const props = defineProps<EdgeProps<StepCanvasEdgeData>>()

const edgePath = computed(
  (): [path: string, labelX: number, labelY: number, offsetX: number, offsetY: number] => {
    const pathOptions = {
      sourceX: props.sourceX,
      sourceY: props.sourceY,
      sourcePosition: props.sourcePosition,
      targetX: props.targetX,
      targetY: props.targetY,
      targetPosition: props.targetPosition
    }
    if (props.data.connectionStyle === 'straight') {
      return getStraightPath(pathOptions)
    }
    if (props.data.connectionStyle === 'step') {
      return getSmoothStepPath({ ...pathOptions, borderRadius: 0, offset: 20 })
    }
    return getBezierPath({ ...pathOptions, curvature: 0.25 })
  }
)

const path = computed((): string => edgePath.value[0])
const labelX = computed((): number => edgePath.value[1])
const labelY = computed((): number => edgePath.value[2])
const edgeStyle = computed(
  (): CSSProperties => ({
    stroke: props.data.visual.color,
    strokeWidth: props.data.graphEdge.annotationOnly ? 1.4 : 1.6,
    strokeDasharray: props.data.visual.dasharray ?? undefined
  })
)
const upperTrackStyle = computed(
  (): CSSProperties => ({
    ...edgeStyle.value,
    transform: 'translateX(-2px)'
  })
)
const lowerTrackStyle = computed(
  (): CSSProperties => ({
    ...edgeStyle.value,
    transform: 'translateX(2px)'
  })
)
</script>

<template>
  <template v-if="data.visual.doubleTrack">
    <BaseEdge
      :id="`${id}:upper`"
      :aria-label="data.title"
      class="step-canvas-edge-path is-parallel"
      :interaction-width="interactionWidth"
      :path="path"
      role="img"
      :style="upperTrackStyle"
      :title="data.title"
    />
    <BaseEdge
      :id="`${id}:lower`"
      :aria-label="data.title"
      class="step-canvas-edge-path is-parallel"
      :interaction-width="interactionWidth"
      :path="path"
      role="img"
      :style="lowerTrackStyle"
      :title="data.title"
    />
  </template>
  <BaseEdge
    v-else
    :id="id"
    :aria-label="data.title"
    class="step-canvas-edge-path"
    :interaction-width="interactionWidth"
    :marker-end="markerEnd"
    :path="path"
    role="img"
    :style="edgeStyle"
    :title="data.title"
  />

  <EdgeLabelRenderer v-if="data.showLabel">
    <div
      class="step-canvas-edge-label nodrag nopan"
      :class="{ 'is-annotation': data.graphEdge.annotationOnly }"
      :style="{
        color: data.visual.color,
        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`
      }"
      :aria-label="data.title"
      :title="data.title"
    >
      {{ data.graphEdge.label }}
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
.step-canvas-edge-label {
  position: absolute;
  max-width: 180px;
  padding: 2px 5px;
  overflow: hidden;
  border: 1px solid currentColor;
  border-radius: 4px;
  opacity: 0.94;
  background: #fff;
  font-size: 9px;
  font-weight: 600;
  line-height: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: all;
  transition: opacity 120ms ease;
}

.step-canvas-edge-label.is-annotation {
  border-style: dashed;
}

@media (prefers-reduced-motion: reduce) {
  .step-canvas-edge-label {
    transition: none;
  }
}
</style>
