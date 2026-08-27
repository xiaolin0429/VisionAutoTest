<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowDownBold,
  ArrowRightBold,
  Collection,
  Document,
  List,
  Operation,
  Search
} from '@element-plus/icons-vue'

import type { StepType } from '@/types/models'
import {
  STEP_CANVAS_PALETTE_MIME,
  type StepCanvasPaletteDragPayload
} from '@/types/stepCanvas'
import type {
  StepGraphNode,
  StepGraphNodeDisplayState,
  StepStructurePath
} from '@/types/stepGraph'
import {
  createStepTypeOptions,
  type StepTypeOption
} from '@/utils/steps'

interface StepLibraryGroup {
  label: string
  types: StepType[]
}

interface StepOutlineRow {
  node: StepGraphNode
  depth: number
  canCollapse: boolean
  collapsed: boolean
  hiddenDescendantCount: number
}

const props = withDefaults(
  defineProps<{
    nodes: readonly StepGraphNode[]
    nodeStates?: Readonly<Record<string, StepGraphNodeDisplayState>>
    selectedPath?: StepStructurePath | null
    collapsed?: boolean
    allowComponentCall?: boolean
  }>(),
  {
    nodeStates: () => ({}),
    selectedPath: null,
    collapsed: false,
    allowComponentCall: true
  }
)

const emit = defineEmits<{
  (event: 'request-expand'): void
  (event: 'create-step', stepType: StepType): void
  (event: 'select-node', path: StepStructurePath): void
  (event: 'toggle-collapse', path: StepStructurePath): void
  (event: 'palette-drag-start', stepType: StepType): void
  (event: 'palette-drag-end'): void
}>()

const activeTab = ref<'library' | 'outline'>('library')
const searchText = ref('')

const libraryGroups: StepLibraryGroup[] = [
  { label: '常用操作', types: ['navigate', 'click', 'input', 'select_option', 'scroll', 'long_press'] },
  { label: '断言', types: ['template_assert', 'ocr_assert'] },
  { label: '流程', types: ['wait', 'conditional_branch', 'component_call'] }
]

const availableOptions = computed((): StepTypeOption[] =>
  createStepTypeOptions({ allowComponentCall: props.allowComponentCall })
)

const optionByType = computed((): ReadonlyMap<StepType, StepTypeOption> =>
  new Map(
    availableOptions.value.map(
      (option: StepTypeOption): [StepType, StepTypeOption] => [option.value, option]
    )
  )
)

const filteredGroups = computed((): StepLibraryGroup[] => {
  const keyword = searchText.value.trim().toLocaleLowerCase()
  return libraryGroups.flatMap((group: StepLibraryGroup): StepLibraryGroup[] => {
    const types = group.types.filter((type: StepType): boolean => {
      const option = optionByType.value.get(type)
      return Boolean(
        option &&
          (!keyword ||
            option.label.toLocaleLowerCase().includes(keyword) ||
            option.value.includes(keyword))
      )
    })
    return types.length > 0 ? [{ ...group, types }] : []
  })
})

const nodeByPath = computed(
  (): ReadonlyMap<StepStructurePath, StepGraphNode> =>
    new Map(
      props.nodes.map(
        (node: StepGraphNode): [StepStructurePath, StepGraphNode] => [
          node.path,
          node
        ]
      )
    )
)

const childrenByPath = computed(
  (): ReadonlyMap<StepStructurePath, StepGraphNode[]> => {
    const children = new Map<StepStructurePath, StepGraphNode[]>()
    props.nodes.forEach((node: StepGraphNode): void => {
      if (!node.parentPath) {
        return
      }
      children.set(node.parentPath, [
        ...(children.get(node.parentPath) ?? []),
        node
      ])
    })
    return children
  }
)

function outlineDepth(node: StepGraphNode): number {
  let depth = 0
  let parentPath = node.parentPath
  while (parentPath) {
    depth += 1
    parentPath = nodeByPath.value.get(parentPath)?.parentPath ?? null
  }
  return depth
}

function countOutlineDescendants(path: StepStructurePath): number {
  return (childrenByPath.value.get(path) ?? []).reduce(
    (total: number, child: StepGraphNode): number =>
      total + 1 + countOutlineDescendants(child.path),
    0
  )
}

function hasCollapsedAncestor(node: StepGraphNode): boolean {
  let parentPath = node.parentPath
  while (parentPath) {
    if (props.nodeStates[parentPath]?.collapsed === true) {
      return true
    }
    parentPath = nodeByPath.value.get(parentPath)?.parentPath ?? null
  }
  return false
}

const outlineRows = computed((): StepOutlineRow[] => {
  const keyword = searchText.value.trim().toLocaleLowerCase()
  return props.nodes.flatMap((node: StepGraphNode): StepOutlineRow[] => {
    if (hasCollapsedAncestor(node)) {
      return []
    }
    if (
      keyword &&
      !`${node.label} ${node.detail}`.toLocaleLowerCase().includes(keyword)
    ) {
      return []
    }
    const canCollapse = (childrenByPath.value.get(node.path)?.length ?? 0) > 0
    const collapsed = props.nodeStates[node.path]?.collapsed === true
    return [{
      node,
      depth: outlineDepth(node),
      canCollapse,
      collapsed,
      hiddenDescendantCount: collapsed
        ? countOutlineDescendants(node.path)
        : 0
    }]
  })
})

function switchCollapsedTab(tab: 'library' | 'outline'): void {
  activeTab.value = tab
  emit('request-expand')
}

function handlePaletteDragStart(event: DragEvent, stepType: StepType): void {
  const payload: StepCanvasPaletteDragPayload = { stepType }
  event.dataTransfer?.setData(
    STEP_CANVAS_PALETTE_MIME,
    JSON.stringify(payload)
  )
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'copy'
  }
  emit('palette-drag-start', stepType)
}

function handlePaletteDragEnd(): void {
  emit('palette-drag-end')
}
</script>

<template>
  <aside class="step-canvas-sidebar" :class="{ 'is-collapsed': collapsed }">
    <template v-if="collapsed">
      <el-tooltip content="节点库" placement="right">
        <button
          aria-label="展开节点库"
          class="sidebar-rail-button"
          type="button"
          @click="switchCollapsedTab('library')"
        >
          <el-icon><Collection /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="执行大纲" placement="right">
        <button
          aria-label="展开执行大纲"
          class="sidebar-rail-button"
          type="button"
          @click="switchCollapsedTab('outline')"
        >
          <el-icon><List /></el-icon>
        </button>
      </el-tooltip>
    </template>

    <template v-else>
      <el-tabs v-model="activeTab" class="sidebar-tabs" stretch>
        <el-tab-pane name="library">
          <template #label>
            <span class="flex items-center gap-1">
              <el-icon><Collection /></el-icon>
              节点库
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="outline">
          <template #label>
            <span class="flex items-center gap-1">
              <el-icon><List /></el-icon>
              大纲
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <el-input
        v-model="searchText"
        :placeholder="activeTab === 'library' ? '搜索步骤类型' : '搜索执行大纲'"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <div v-if="activeTab === 'library'" class="sidebar-scroll-region">
        <section
          v-for="group in filteredGroups"
          :key="group.label"
          class="library-group"
        >
          <h3>{{ group.label }}</h3>
          <div class="library-grid">
            <button
              v-for="type in group.types"
              :key="type"
              :aria-label="`添加${optionByType.get(type)?.label ?? type}步骤`"
              class="library-item"
              draggable="true"
              :title="`拖入画布或点击添加${optionByType.get(type)?.label ?? type}步骤`"
              type="button"
              @click="emit('create-step', type)"
              @dragend="handlePaletteDragEnd"
              @dragstart="handlePaletteDragStart($event, type)"
            >
              <el-icon aria-hidden="true"><Operation /></el-icon>
              <span>{{ optionByType.get(type)?.label ?? type }}</span>
            </button>
          </div>
        </section>
      </div>

      <div v-else class="sidebar-scroll-region outline-list" role="tree">
        <div
          v-for="row in outlineRows"
          :key="row.node.path"
          :aria-expanded="row.canCollapse ? !row.collapsed : undefined"
          :aria-level="row.depth + 1"
          class="outline-row"
          role="treeitem"
          :style="{ paddingLeft: `${4 + row.depth * 14}px` }"
        >
          <button
            v-if="row.canCollapse"
            :aria-label="row.collapsed
              ? `展开${row.node.label}，当前隐藏 ${row.hiddenDescendantCount} 个节点`
              : `折叠${row.node.label}`"
            class="outline-collapse-button"
            :title="row.collapsed
              ? `展开，当前隐藏 ${row.hiddenDescendantCount} 个节点`
              : '折叠子节点'"
            type="button"
            @click="emit('toggle-collapse', row.node.path)"
          >
            <el-icon aria-hidden="true">
              <ArrowRightBold v-if="row.collapsed" />
              <ArrowDownBold v-else />
            </el-icon>
          </button>
          <span v-else aria-hidden="true" class="outline-collapse-placeholder" />
          <button
          :aria-current="row.node.path === selectedPath ? 'true' : undefined"
          class="outline-item"
          :class="{ 'is-active': row.node.path === selectedPath }"
          :title="`${row.node.label} · ${row.node.detail}`"
          type="button"
          @click="emit('select-node', row.node.path)"
          >
          <el-icon aria-hidden="true">
            <Document v-if="row.node.kind !== 'root'" />
            <List v-else />
          </el-icon>
          <span class="min-w-0">
            <strong :title="row.node.label">{{ row.node.label }}</strong>
            <small :title="row.node.detail">
              {{ row.node.detail }}
              <template v-if="row.hiddenDescendantCount > 0">
                · 隐藏 {{ row.hiddenDescendantCount }}
              </template>
            </small>
          </span>
          </button>
        </div>
        <p v-if="outlineRows.length === 0" class="m-0 px-2 py-6 text-center text-xs text-slate-400">
          未找到匹配节点
        </p>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.step-canvas-sidebar {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 10px;
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
  background: #fff;
}

.step-canvas-sidebar.is-collapsed {
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
}

.sidebar-rail-button {
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

.sidebar-rail-button:hover,
.sidebar-rail-button:focus-visible {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.sidebar-tabs {
  margin: -6px 0 -10px;
}

.sidebar-scroll-region {
  min-height: 0;
  overflow: auto;
}

.library-group + .library-group {
  margin-top: 16px;
}

.library-group h3 {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.library-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #334155;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}

.library-item:hover,
.library-item:focus-visible {
  border-color: #93c5fd;
  color: #1d4ed8;
  background: #f8fbff;
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.outline-list {
  margin: 0 -4px;
}

.outline-row {
  display: flex;
  min-width: 0;
  align-items: center;
}

.outline-collapse-button,
.outline-collapse-placeholder {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
}

.outline-collapse-button {
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 4px;
  color: #64748b;
  background: transparent;
  cursor: pointer;
}

.outline-collapse-button:hover,
.outline-collapse-button:focus-visible {
  color: #1d4ed8;
  background: #dbeafe;
  outline: 2px solid #1d4ed8;
  outline-offset: -1px;
}

.outline-item {
  display: flex;
  width: calc(100% - 22px);
  min-width: 0;
  align-items: flex-start;
  gap: 7px;
  padding-top: 8px;
  padding-right: 8px;
  padding-bottom: 8px;
  border: 0;
  border-radius: 6px;
  color: #475569;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.outline-item:hover,
.outline-item:focus-visible,
.outline-item.is-active {
  color: #1d4ed8;
  background: #eff6ff;
}

.outline-item:focus-visible {
  outline: 2px solid #1d4ed8;
  outline-offset: -2px;
}

.outline-item strong,
.outline-item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-item strong {
  font-size: 12px;
  font-weight: 600;
}

.outline-item small {
  margin-top: 2px;
  color: #64748b;
  font-size: 11px;
}

.step-canvas-sidebar :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.step-canvas-sidebar :deep(.el-input__wrapper) {
  border-radius: 6px;
}
</style>
