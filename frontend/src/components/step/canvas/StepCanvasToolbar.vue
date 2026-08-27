<script setup lang="ts">
import { ref, useId } from 'vue'
import {
  Aim,
  ArrowLeft,
  Collection,
  Expand,
  Fold,
  MoreFilled,
  Operation,
  RefreshLeft,
  RefreshRight,
  Setting
} from '@element-plus/icons-vue'

import type { StepCanvasViewportMode } from '@/composables/useStepCanvasViewport'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    mode: StepCanvasViewportMode
    dirty?: boolean
    saving?: boolean
    canUndo?: boolean
    canRedo?: boolean
    leftCollapsed?: boolean
    inspectorCollapsed?: boolean
    viewportReady?: boolean
  }>(),
  {
    subtitle: '',
    dirty: false,
    saving: false,
    canUndo: false,
    canRedo: false,
    leftCollapsed: false,
    inspectorCollapsed: false,
    viewportReady: true
  }
)

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'undo'): void
  (event: 'redo'): void
  (event: 'auto-layout'): void
  (event: 'fit-view'): void
  (event: 'save'): void
  (event: 'toggle-library'): void
  (event: 'toggle-inspector'): void
}>()

const toolbarRef = ref<HTMLElement | null>(null)
const viewportStatusId = `step-canvas-viewport-status-${useId()}`
const viewportInitializingMessage = '画布视口正在初始化，请稍候。'

function viewportCommandTitle(label: string): string {
  return props.viewportReady ? label : viewportInitializingMessage
}

function handleCompactCommand(command: string | number | object): void {
  if (command === 'auto-layout' && props.viewportReady) {
    emit('auto-layout')
  } else if (command === 'fit-view' && props.viewportReady) {
    emit('fit-view')
  } else if (command === 'toggle-library') {
    emit('toggle-library')
  } else if (command === 'toggle-inspector') {
    emit('toggle-inspector')
  }
}

function moveToolbarFocus(event: KeyboardEvent, direction: -1 | 1): void {
  const toolbar = toolbarRef.value
  const target = event.target
  if (!toolbar || !(target instanceof Element)) {
    return
  }
  const buttons = Array.from(
    toolbar.querySelectorAll<HTMLButtonElement>('button:not([disabled])')
  ).filter(
    (button: HTMLButtonElement): boolean =>
      button.getAttribute('aria-disabled') !== 'true' && button.tabIndex >= 0
  )
  if (buttons.length === 0) {
    return
  }
  const currentButton = target.closest<HTMLButtonElement>('button')
  const currentIndex = currentButton ? buttons.indexOf(currentButton) : -1
  const nextIndex =
    currentIndex < 0
      ? 0
      : (currentIndex + direction + buttons.length) % buttons.length
  event.preventDefault()
  event.stopPropagation()
  buttons[nextIndex].focus()
}
</script>

<template>
  <header
    ref="toolbarRef"
    aria-label="步骤画布命令"
    class="step-canvas-toolbar"
    role="toolbar"
    @keydown.left="moveToolbarFocus($event, -1)"
    @keydown.right="moveToolbarFocus($event, 1)"
  >
    <span
      :id="viewportStatusId"
      class="sr-only"
      aria-live="polite"
      role="status"
    >
      {{ viewportReady ? '画布视口已就绪。' : viewportInitializingMessage }}
    </span>

    <div class="flex min-w-0 items-center gap-2">
      <el-tooltip content="关闭画布" placement="bottom">
        <el-button
          :icon="ArrowLeft"
          aria-label="关闭画布"
          circle
          text
          @click="emit('close')"
        />
      </el-tooltip>
      <div class="min-w-0">
        <div class="flex min-w-0 items-center gap-2">
          <strong class="truncate text-sm font-semibold text-slate-900">
            {{ title }}
          </strong>
          <span
            v-if="dirty"
            class="shrink-0 text-xs font-medium text-amber-700"
            role="status"
          >
            ● 未保存
          </span>
        </div>
        <p
          v-if="subtitle && mode !== 'compact'"
          class="m-0 truncate text-xs text-slate-500"
        >
          {{ subtitle }}
        </p>
      </div>
    </div>

    <div class="flex shrink-0 items-center gap-2">
      <template v-if="mode !== 'compact'">
        <el-tooltip :content="leftCollapsed ? '展开节点库' : '折叠节点库'" placement="bottom">
          <el-button
            :icon="leftCollapsed ? Expand : Fold"
            aria-label="切换节点库"
            circle
            plain
            @click="emit('toggle-library')"
          />
        </el-tooltip>
        <el-button-group>
          <el-tooltip content="撤销" placement="bottom">
            <el-button
              :disabled="!canUndo"
              :icon="RefreshLeft"
              aria-label="撤销"
              @click="emit('undo')"
            />
          </el-tooltip>
          <el-tooltip content="重做" placement="bottom">
            <el-button
              :disabled="!canRedo"
              :icon="RefreshRight"
              aria-label="重做"
              @click="emit('redo')"
            />
          </el-tooltip>
        </el-button-group>
        <el-tooltip :content="viewportCommandTitle('自动布局')" placement="bottom">
          <el-button
            :aria-describedby="viewportReady ? undefined : viewportStatusId"
            :disabled="!viewportReady"
            :icon="Operation"
            aria-label="自动布局"
            plain
            :title="viewportCommandTitle('自动布局')"
            @click="emit('auto-layout')"
          >
            <span v-if="mode === 'desktop'">自动布局</span>
          </el-button>
        </el-tooltip>
        <el-tooltip :content="viewportCommandTitle('适应视图')" placement="bottom">
          <el-button
            :aria-describedby="viewportReady ? undefined : viewportStatusId"
            :disabled="!viewportReady"
            :icon="Aim"
            aria-label="适应视图"
            plain
            :title="viewportCommandTitle('适应视图')"
            @click="emit('fit-view')"
          />
        </el-tooltip>
        <slot name="background-control" />
        <el-tooltip
          :content="inspectorCollapsed ? '展开检查器' : '折叠检查器'"
          placement="bottom"
        >
          <el-button
            :icon="inspectorCollapsed ? Collection : Setting"
            aria-label="切换检查器"
            circle
            plain
            @click="emit('toggle-inspector')"
          />
        </el-tooltip>
      </template>

      <template v-else>
        <slot name="background-control" />
        <el-dropdown trigger="click" @command="handleCompactCommand">
          <el-button :icon="MoreFilled" aria-label="更多画布操作" circle plain />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="toggle-library">打开节点库</el-dropdown-item>
              <el-dropdown-item command="toggle-inspector">打开检查器</el-dropdown-item>
              <el-dropdown-item :disabled="!viewportReady" command="auto-layout">
                自动布局{{ viewportReady ? '' : '（画布初始化中）' }}
              </el-dropdown-item>
              <el-dropdown-item :disabled="!viewportReady" command="fit-view">
                适应视图{{ viewportReady ? '' : '（画布初始化中）' }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>

      <slot name="secondary-actions" />
      <el-button
        :loading="saving"
        color="#2563eb"
        @click="emit('save')"
      >
        {{ mode === 'compact' ? '保存' : '保存步骤' }}
      </el-button>
    </div>
  </header>
</template>

<style scoped>
.step-canvas-toolbar {
  box-sizing: border-box;
  display: grid;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  height: 52px;
  padding: 0 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

@media (max-width: 959px) {
  .step-canvas-toolbar {
    height: 56px;
    padding: 0 8px;
  }
}

.step-canvas-toolbar :deep(.el-button) {
  border-radius: 6px;
}

.step-canvas-toolbar :deep(.el-button.is-circle) {
  border-radius: 50%;
}

.step-canvas-toolbar :deep(.el-button:focus-visible) {
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 24%);
}
</style>
