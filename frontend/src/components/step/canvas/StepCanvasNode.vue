<script setup lang="ts">
import { computed, type Component, type CSSProperties } from 'vue'
import {
  ArrowDownBold,
  ArrowRightBold,
  CircleCheck,
  Clock,
  Connection,
  CopyDocument,
  EditPen,
  Files,
  Guide,
  Link,
  Location,
  Lock,
  MoreFilled,
  Operation,
  Plus,
  Pointer,
  Rank,
  Share,
  Sort,
  View,
  WarningFilled
} from '@element-plus/icons-vue'
import { Handle, Position, type NodeProps } from '@vue-flow/core'

import type { StepCanvasNodeData } from '@/types/stepCanvas'
import type { StepType } from '@/types/models'
import type { EditableStepPath, StepGraphNode } from '@/types/stepGraph'

const props = defineProps<NodeProps<StepCanvasNodeData>>()

const stepIcons: Record<StepType, Component> = {
  wait: Clock,
  click: Pointer,
  input: EditPen,
  select_option: Operation,
  template_assert: CircleCheck,
  ocr_assert: View,
  component_call: Link,
  navigate: Location,
  scroll: Sort,
  long_press: Rank,
  conditional_branch: Share
}

const node = computed((): StepGraphNode => props.data.graphNode)
const isRoot = computed((): boolean => node.value.kind === 'root')
const isLane = computed(
  (): boolean =>
    node.value.kind === 'branch-lane' || node.value.kind === 'else-lane'
)
const isConditional = computed(
  (): boolean =>
    node.value.kind === 'top-step' &&
    node.value.stepType === 'conditional_branch'
)
const isComponent = computed(
  (): boolean =>
    node.value.stepType === 'component_call' ||
    node.value.kind === 'component-preview'
)
const nodeIcon = computed(
  (): Component =>
    isRoot.value
      ? Files
      : isLane.value
        ? Guide
        : node.value.stepType
          ? stepIcons[node.value.stepType]
          : Connection
)
const nodeStyle = computed(
  (): CSSProperties & Record<string, string> => ({
    '--node-background': props.data.palette.background,
    '--node-border': node.value.errorCount > 0 ? '#e11d48' : props.data.palette.border,
    '--node-radius': props.data.shape === 'rounded' ? '8px' : '4px'
  })
)
const fullTooltip = computed((): string => {
  const parts = [node.value.label, node.value.summary]
  if (node.value.timeoutMs !== null) {
    parts.push(`超时 ${node.value.timeoutMs} ms`)
  }
  if (node.value.retryTimes !== null) {
    parts.push(`重试 ${node.value.retryTimes}`)
  }
  if (node.value.errorCount > 0) {
    parts.push(`${node.value.errorCount} 个配置错误`)
  }
  return parts.join(' · ')
})
const stepNumber = computed(
  (): string =>
    node.value.stepNo === null ? '--' : String(node.value.stepNo).padStart(2, '0')
)
const targetHandleLabel = computed((): string => {
  if (node.value.kind === 'branch-lane') {
    return `条件分支“${node.value.label}”命中输入端口`
  }
  if (node.value.kind === 'else-lane') {
    return `默认分支“${node.value.label}”输入端口`
  }
  if (node.value.kind === 'component-preview') {
    return `组件预览步骤“${node.value.label}”引用输入端口`
  }
  return `步骤“${node.value.label}”顺序执行输入端口`
})
const sourceHandleLabel = computed((): string => {
  if (isRoot.value) {
    return `用例根节点“${node.value.label}”流程输出端口`
  }
  if (isConditional.value) {
    return `条件步骤“${node.value.label}”分支输出端口`
  }
  if (isLane.value) {
    return `分支“${node.value.label}”步骤输出端口`
  }
  if (node.value.kind === 'component-preview') {
    return `组件预览步骤“${node.value.label}”顺序输出端口`
  }
  if (node.value.stepType === 'component_call') {
    return `组件调用“${node.value.label}”顺序与预览输出端口`
  }
  return `步骤“${node.value.label}”顺序执行输出端口`
})

function toggleCollapse(): void {
  props.data.onToggleCollapse(node.value.path)
}

function addAfter(): void {
  if (node.value.editable) {
    props.data.onAddAfter(node.value.path as EditableStepPath)
  }
}

function duplicate(): void {
  if (node.value.editable) {
    props.data.onDuplicate(node.value.path as EditableStepPath)
  }
}

function openMore(): void {
  if (node.value.editable) {
    props.data.onMore(node.value.path as EditableStepPath)
  }
}

function openInspector(): void {
  props.data.onOpenInspector(node.value.path)
}

function openComponent(): void {
  if (node.value.componentId !== null) {
    props.data.onOpenComponent(node.value.componentId)
  }
}
</script>

<template>
  <div
    class="step-execution-node"
    :class="{
      'is-root': isRoot,
      'is-lane': isLane,
      'is-conditional': isConditional,
      'is-component': isComponent,
      'is-read-only': node.readOnly,
      'is-selected': selected,
      'is-dragging': dragging,
      'has-errors': node.errorCount > 0
    }"
    :aria-invalid="node.errorCount > 0 ? 'true' : undefined"
    :aria-label="fullTooltip"
    :aria-readonly="node.readOnly ? 'true' : undefined"
    :aria-selected="selected ? 'true' : 'false'"
    :style="nodeStyle"
    :title="fullTooltip"
    aria-keyshortcuts="Enter"
    role="button"
    tabindex="0"
    @dblclick.stop="openInspector"
    @keydown.enter.stop="openInspector"
  >
    <Handle
      v-if="!isRoot"
      :aria-label="targetHandleLabel"
      class="execution-handle"
      :connectable="false"
      :position="Position.Top"
      role="img"
      :title="targetHandleLabel"
      type="target"
    />

    <template v-if="isRoot">
      <div class="node-card root-card">
        <div class="node-header">
          <span class="node-type">
            <el-icon aria-hidden="true"><component :is="nodeIcon" /></el-icon>
            {{ node.typeLabel }}
          </span>
          <button
            v-if="data.canCollapse"
            class="node-icon-button nodrag"
            :aria-label="data.collapsed ? '展开用例步骤' : '折叠用例步骤'"
            type="button"
            @click.stop="toggleCollapse"
          >
            <el-icon aria-hidden="true">
              <ArrowRightBold v-if="data.collapsed" />
              <ArrowDownBold v-else />
            </el-icon>
          </button>
        </div>
        <strong class="node-name" :title="node.label">{{ node.label }}</strong>
        <span class="node-summary" :title="node.summary">{{ node.summary }}</span>
        <span v-if="node.hiddenDescendantCount > 0" class="hidden-count">
          隐藏 {{ node.hiddenDescendantCount }} 个节点
        </span>
      </div>
    </template>

    <template v-else-if="isLane">
      <div class="node-card lane-card">
        <div class="node-header">
          <span class="node-type">
            <el-icon aria-hidden="true"><component :is="nodeIcon" /></el-icon>
            {{ node.typeLabel }}
          </span>
          <button
            v-if="data.canCollapse"
            class="node-icon-button nodrag"
            :aria-label="data.collapsed ? '展开分支泳道' : '折叠分支泳道'"
            type="button"
            @click.stop="toggleCollapse"
          >
            <el-icon aria-hidden="true">
              <ArrowRightBold v-if="data.collapsed" />
              <ArrowDownBold v-else />
            </el-icon>
          </button>
        </div>
        <strong class="node-name" :title="node.label">{{ node.label }}</strong>
        <span class="node-summary" :title="node.summary">{{ node.summary }}</span>
        <span v-if="node.hiddenDescendantCount > 0" class="hidden-count">
          隐藏 {{ node.hiddenDescendantCount }} 个节点
        </span>
      </div>
    </template>

    <template v-else>
      <div class="node-card step-card">
        <div class="node-header">
          <span class="step-number">{{ stepNumber }}</span>
          <span class="node-type">
            <el-icon aria-hidden="true"><component :is="nodeIcon" /></el-icon>
            {{ node.typeLabel }}
          </span>
          <span
            v-if="node.readOnly"
            aria-label="组件预览步骤只读，不能在用例画布编辑"
            title="组件预览步骤只读，不能在用例画布编辑"
          >
            <el-icon aria-hidden="true" class="read-only-icon"><Lock /></el-icon>
          </span>
          <button
            v-if="data.canCollapse"
            class="node-icon-button nodrag"
            :aria-label="data.collapsed ? '展开子节点' : '折叠子节点'"
            type="button"
            @click.stop="toggleCollapse"
          >
            <el-icon aria-hidden="true">
              <ArrowRightBold v-if="data.collapsed" />
              <ArrowDownBold v-else />
            </el-icon>
          </button>
        </div>

        <strong class="node-name" :title="node.label">{{ node.label }}</strong>
        <span class="node-summary" :title="node.summary">{{ node.summary }}</span>

        <div class="node-meta">
          <span v-if="node.timeoutMs !== null">超时 {{ node.timeoutMs }}ms</span>
          <span v-if="node.retryTimes !== null">重试 {{ node.retryTimes }}</span>
          <span v-if="node.componentStatus" class="component-status">
            {{ node.componentStatus }}
          </span>
          <button
            v-if="isComponent && node.componentId !== null"
            :aria-label="`查看组件详情：${node.detail}`"
            class="component-detail-button nodrag"
            :title="`查看组件详情：${node.detail}`"
            type="button"
            @click.stop="openComponent"
          >
            查看组件详情
          </button>
          <span v-if="node.hiddenDescendantCount > 0" class="hidden-count">
            隐藏 {{ node.hiddenDescendantCount }}
          </span>
        </div>

        <span
          v-if="node.errorCount > 0"
          :aria-label="`${node.errorCount} 个配置错误`"
          :title="`${node.errorCount} 个配置错误`"
        >
          <span class="error-badge" role="status">
            <el-icon aria-hidden="true"><WarningFilled /></el-icon>
            {{ node.errorCount }} 个配置错误
          </span>
        </span>

        <div v-if="node.editable" class="node-hover-tools nodrag">
          <button aria-label="新增后继" title="新增后继" type="button" @click.stop="addAfter">
            <el-icon aria-hidden="true"><Plus /></el-icon>
          </button>
          <button aria-label="复制节点" title="复制节点" type="button" @click.stop="duplicate">
            <el-icon aria-hidden="true"><CopyDocument /></el-icon>
          </button>
          <button aria-label="更多节点操作" title="更多节点操作" type="button" @click.stop="openMore">
            <el-icon aria-hidden="true"><MoreFilled /></el-icon>
          </button>
        </div>
      </div>
    </template>

    <span v-if="selected" aria-hidden="true" class="selection-corner corner-tl" />
    <span v-if="selected" aria-hidden="true" class="selection-corner corner-tr" />
    <span v-if="selected" aria-hidden="true" class="selection-corner corner-bl" />
    <span v-if="selected" aria-hidden="true" class="selection-corner corner-br" />

    <Handle
      :aria-label="sourceHandleLabel"
      class="execution-handle"
      :connectable="false"
      :position="Position.Bottom"
      role="img"
      :title="sourceHandleLabel"
      type="source"
    />
  </div>
</template>

<style scoped>
.step-execution-node {
  position: relative;
  width: 100%;
  height: 100%;
  color: #0f172a;
  cursor: grab;
  outline: none;
  transition:
    transform 150ms ease,
    opacity 150ms ease;
}

.step-execution-node:focus-visible .node-card {
  outline: 3px solid #1d4ed8;
  outline-offset: 3px;
}

.step-execution-node.is-dragging {
  opacity: 0.48;
  transform: scale(0.98);
  cursor: grabbing;
}

.step-execution-node.is-read-only,
.step-execution-node.is-lane,
.step-execution-node.is-root {
  cursor: default;
}

.node-card {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  flex-direction: column;
  justify-content: center;
  padding: 10px 12px;
  overflow: visible;
  border: 1px solid var(--node-border);
  border-radius: var(--node-radius);
  background: var(--node-background);
  box-shadow: 0 2px 8px rgb(15 23 42 / 8%);
}

.is-selected .node-card {
  border-width: 2px;
  border-color: #2563eb;
}

.is-read-only .node-card {
  border-style: dashed;
  box-shadow: none;
}

.is-conditional .node-card {
  padding-right: 34px;
  padding-left: 34px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.is-conditional .node-card::before,
.is-conditional .node-card::after {
  position: absolute;
  content: '';
  clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%);
  pointer-events: none;
}

.is-conditional .node-card::before {
  z-index: 0;
  inset: 1px 13px;
  background: var(--node-border);
}

.is-conditional .node-card::after {
  z-index: 0;
  inset: 3px 16px;
  background: var(--node-background);
}

.is-conditional.is-selected .node-card::before {
  background: #2563eb;
}

.is-conditional .node-card > * {
  z-index: 1;
}

.lane-card {
  padding: 8px 10px;
  border-style: dashed;
  box-shadow: none;
}

.root-card {
  background: #f8fafc;
}

.node-header {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  color: #475569;
  font-size: 10px;
  line-height: 16px;
}

.step-number {
  flex: 0 0 auto;
  color: #334155;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.node-type {
  display: inline-flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-icon-button {
  display: grid;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 4px;
  color: #64748b;
  background: transparent;
  cursor: pointer;
}

.node-icon-button:hover,
.node-icon-button:focus-visible {
  color: #1d4ed8;
  background: #dbeafe;
  outline: 2px solid #1d4ed8;
  outline-offset: 1px;
}

.node-name,
.node-summary {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  text-align: left;
  text-overflow: ellipsis;
}

.node-name {
  margin-top: 2px;
  -webkit-line-clamp: 1;
  color: #0f172a;
  font-size: 13px;
  line-height: 18px;
}

.node-summary {
  -webkit-line-clamp: 1;
  color: #475569;
  font-size: 10px;
  line-height: 15px;
}

.node-meta {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  overflow: hidden;
  color: #475569;
  font-size: 9px;
  line-height: 13px;
  white-space: nowrap;
}

.component-status {
  color: #4338ca;
  font-weight: 600;
}

.component-detail-button {
  padding: 0;
  border: 0;
  color: #4338ca;
  background: transparent;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.component-detail-button:hover,
.component-detail-button:focus-visible {
  color: #1d4ed8;
  text-decoration: underline;
  outline: 2px solid #1d4ed8;
  outline-offset: 1px;
}

.hidden-count {
  color: #b45309;
  font-size: 9px;
  font-weight: 600;
  white-space: nowrap;
}

.read-only-icon {
  flex: 0 0 auto;
  color: #6366f1;
}

.error-badge {
  position: absolute;
  z-index: 3;
  top: -8px;
  right: -8px;
  display: inline-flex;
  min-width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 0 5px;
  border: 2px solid #fff;
  border-radius: 8px;
  color: #fff;
  background: #e11d48;
  font-size: 9px;
  font-weight: 700;
}

.node-hover-tools {
  position: absolute;
  z-index: 5;
  top: -34px;
  right: 0;
  display: flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  opacity: 0;
  background: #fff;
  box-shadow: 0 2px 8px rgb(15 23 42 / 12%);
  pointer-events: none;
  transform: translateY(4px);
  transition:
    transform 140ms ease,
    opacity 140ms ease;
}

.step-execution-node:hover .node-hover-tools,
.step-execution-node:focus-within .node-hover-tools {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.node-hover-tools button {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 4px;
  color: #475569;
  background: transparent;
  cursor: pointer;
}

.node-hover-tools button:hover,
.node-hover-tools button:focus-visible {
  color: #1d4ed8;
  background: #eff6ff;
  outline: 2px solid #1d4ed8;
  outline-offset: 1px;
}

.selection-corner {
  position: absolute;
  z-index: 6;
  width: 6px;
  height: 6px;
  border: 1px solid #fff;
  border-radius: 2px;
  background: #2563eb;
  pointer-events: none;
}

.corner-tl {
  top: -3px;
  left: -3px;
}

.corner-tr {
  top: -3px;
  right: -3px;
}

.corner-bl {
  bottom: -3px;
  left: -3px;
}

.corner-br {
  right: -3px;
  bottom: -3px;
}

.execution-handle {
  width: 7px;
  height: 7px;
  border: 1px solid #fff;
  background: var(--node-border);
  pointer-events: none;
}

@media (prefers-reduced-motion: reduce) {
  .step-execution-node,
  .node-hover-tools {
    transition: none;
  }
}
</style>
