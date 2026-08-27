<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  useSlots,
  watch,
  type CSSProperties
} from 'vue'
import {
  Close,
  FullScreen,
  ZoomIn,
  ZoomOut
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  MarkerType,
  Position,
  VueFlow,
  type Edge,
  type Node,
  type NodeChange,
  type NodeDragEvent,
  type NodeMouseEvent,
  type ViewportTransform,
  type VueFlowStore
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { ControlButton, Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useMediaQuery } from '@vueuse/core'

import StepCanvasBackgroundControl from './StepCanvasBackgroundControl.vue'
import StepCanvasEdge from './StepCanvasEdge.vue'
import StepCanvasInspectorPanel, {
  type StepCanvasInspectorTab
} from './StepCanvasInspectorPanel.vue'
import StepCanvasInspectorContent, {
  type StepCanvasInspectorCommand
} from './StepCanvasInspectorContent.vue'
import StepCanvasLegend from './StepCanvasLegend.vue'
import StepCanvasNode from './StepCanvasNode.vue'
import StepCanvasSidebar from './StepCanvasSidebar.vue'
import StepCanvasStatusBar from './StepCanvasStatusBar.vue'
import StepCanvasToolbar from './StepCanvasToolbar.vue'
import { useStepCanvasEditor } from '@/composables/useStepCanvasEditor'
import {
  useStepCanvasPreferences,
  type StepCanvasBackgroundPatch,
  type StepCanvasStorageScope
} from '@/composables/useStepCanvasPreferences'
import {
  useStepCanvasViewportMode,
  type StepCanvasViewportMode
} from '@/composables/useStepCanvasViewport'
import type { Component, StepType, Template } from '@/types/models'
import type {
  StepCanvasEdgeData,
  StepCanvasNodeData,
  StepCanvasPaletteDragPayload,
  StepCanvasStepsChange,
  StepCanvasValidationError
} from '@/types/stepCanvas'
import { STEP_CANVAS_PALETTE_MIME } from '@/types/stepCanvas'
import type {
  EditableStepPath,
  StepGraphAnnotation,
  StepGraphAnnotationKind,
  StepGraph,
  StepGraphComponentPreview,
  StepGraphDisplayState,
  StepGraphEdge,
  StepGraphMutationResult,
  StepGraphNode,
  StepGraphNodeDisplayState,
  StepGraphPosition,
  StepGraphProjectionOptions,
  StepContainerPath,
  StepStructurePath
} from '@/types/stepGraph'
import {
  assessStepDraftDrop,
  assessStepDraftInsertion,
  applyStepGraphDisplayState,
  filterCollapsedStepGraph,
  getStepContainerLength,
  getStepContainerPath,
  getStepGraphEdgeVisual,
  insertStepDraft,
  isEditableStepPath,
  layoutStepGraph,
  migrateStepGraphDisplayState,
  moveStepDraftAtInsertion,
  parseStepStructurePath,
  projectStepDraftsToGraph,
  reorderStepDrafts,
  shouldShowStepGraphEdgeLabels
} from '@/utils/stepGraph'
import {
  copyStepDraftSelection,
  deleteStepDraftSelection,
  pasteStepDraftClipboard,
  regenerateStepDraftTemporaryIds,
  type StepCanvasClipboard
} from '@/utils/stepCanvasClipboard'
import {
  resolveStepCanvasShortcut,
  type StepCanvasShortcutCommand
} from '@/utils/stepCanvasShortcuts'
import { setStepCanvasBodyMode } from '@/utils/stepCanvasBodyMode'
import {
  createStepGraphIncrementalPipeline,
  type StepGraphIncrementalResult
} from '@/utils/stepGraphIncremental'
import {
  createEmptyStepDraft,
  normalizeStepByType,
  validateStepDraft,
  type ConditionalBranchDraft,
  type StepDraft,
  type StepTemplateOption,
  type StepValidationErrors
} from '@/utils/steps'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

interface StepCanvasMoveEvent {
  flowTransform: ViewportTransform
}

interface StepCanvasDropCandidate {
  mode: 'move' | 'create'
  targetContainerPath: StepContainerPath
  insertionIndex: number
  x: number
  y: number
  width: number
  valid: boolean
  reason: string
}

interface StepCanvasDragOrigin {
  path: EditableStepPath
  position: StepGraphPosition
}

export interface StepCanvasEditorError {
  message: string
  path: EditableStepPath | null
  source: 'validation' | 'command' | 'preference'
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    userId: number
    workspaceId: number
    testCaseId: number
    stepDrafts: readonly StepDraft[]
    title?: string
    testCaseCode?: string
    componentPreviews?: Readonly<Record<number, StepGraphComponentPreview>>
    templates?: Template[]
    components?: Component[]
    selectedPath?: StepStructurePath | null
    allowComponentCall?: boolean
    dirty?: boolean
    saving?: boolean
    canUndo?: boolean
    canRedo?: boolean
    errorCount?: number
    statusMessage?: string
    validateStepFn?: (step: StepDraft) => StepValidationErrors
    getStepTemplateOptionsFn?: (step: StepDraft) => StepTemplateOption[]
    getStepTemplateHintFn?: (step: StepDraft) => string
    formatComponentOptionLabelFn?: (component: Component) => string
  }>(),
  {
    title: '步骤画布',
    testCaseCode: '',
    componentPreviews: () => ({}),
    templates: () => [],
    components: () => [],
    selectedPath: null,
    allowComponentCall: true,
    dirty: false,
    saving: false,
    canUndo: false,
    canRedo: false,
    errorCount: 0,
    statusMessage: '',
    validateStepFn: validateStepDraft,
    getStepTemplateOptionsFn: undefined,
    getStepTemplateHintFn: undefined,
    formatComponentOptionLabelFn: undefined
  }
)

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'update:selectedPath', value: StepStructurePath | null): void
  (event: 'request-close'): void
  (event: 'closed'): void
  (event: 'save', value: StepDraft[]): void
  (event: 'undo'): void
  (event: 'redo'): void
  (event: 'create-step', stepType: StepType): void
  (event: 'request-create-after', path: EditableStepPath): void
  (event: 'node-action', path: EditableStepPath): void
  (event: 'update:stepDrafts', value: StepDraft[]): void
  (event: 'update:step-drafts', value: StepDraft[]): void
  (event: 'dirty-change', value: boolean): void
  (event: 'locate', path: EditableStepPath): void
  (event: 'error', value: StepCanvasEditorError): void
  (event: 'steps-change', value: StepDraft[], change: StepCanvasStepsChange): void
  (event: 'select-node', path: StepStructurePath | null): void
  (event: 'node-position-change', path: StepStructurePath, position: StepGraphPosition): void
  (event: 'display-state-change', state: StepGraphDisplayState): void
  (event: 'background-error', message: string): void
  (event: 'show-errors'): void
  (event: 'open-component', componentId: number): void
  (event: 'request-component-previews', componentIds: number[]): void
  (event: 'ready'): void
}>()

const slots = useSlots()
const viewportMode = useStepCanvasViewportMode()
const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
const flowStore = ref<VueFlowStore | null>(null)
const viewportReady = ref(false)
const viewport = ref<ViewportTransform>({ x: 0, y: 0, zoom: 1 })
const internalSelectedPath = ref<StepStructurePath | null>(props.selectedPath)
const selectedPaths = ref<Set<StepStructurePath>>(
  new Set(props.selectedPath ? [props.selectedPath] : [])
)
const inspectorTab = ref<StepCanvasInspectorTab>('config')
const leftCollapsed = ref(false)
const inspectorCollapsed = ref(false)
const mobileLibraryOpen = ref(false)
const mobileInspectorOpen = ref(false)
const backgroundBusy = ref(false)
const projectionError = ref('')
const commandStatusMessage = ref('')
const dropCandidate = ref<StepCanvasDropCandidate | null>(null)
const dragOrigin = ref<StepCanvasDragOrigin | null>(null)
const paletteDragType = ref<StepType | null>(null)
const syncingFlowSelection = ref(false)
const clipboard = ref<StepCanvasClipboard | null>(null)
const selectedBranchDraftId = ref<number | null>(null)
const inputElementKeys = new WeakMap<Element, string>()
const bodyModeOwner = Symbol('step-canvas-body-mode')
const canvasMinZoom = 0.2
const canvasMaxZoom = 2
let inputElementSequence = 0

const storageScope = computed(
  (): StepCanvasStorageScope => ({
    userId: props.userId,
    workspaceId: props.workspaceId,
    testCaseId: props.testCaseId
  })
)

const {
  displayState,
  backgroundImageUrl,
  loaded: preferencesLoaded,
  preferenceError,
  replaceDisplayState,
  patchBackground,
  saveBackgroundImage,
  clearBackgroundImage
} = useStepCanvasPreferences(storageScope)

const editor = useStepCanvasEditor({
  displayState,
  replaceDisplayState,
  onDraftsChange(drafts: StepDraft[]): void {
    emit('update:stepDrafts', drafts)
    emit('update:step-drafts', drafts)
  },
  onDirtyChange(value: boolean): void {
    emit('dirty-change', value)
  }
})
const workingStepDrafts = editor.stepDrafts
editor.initialize(props.stepDrafts)

const businessDirty = computed(
  (): boolean => editor.dirty.value || props.dirty
)
const commandCanUndo = computed(
  (): boolean => editor.canUndo.value || props.canUndo
)
const commandCanRedo = computed(
  (): boolean => editor.canRedo.value || props.canRedo
)

function resolveStepDraftAtPath(
  drafts: readonly StepDraft[],
  path: EditableStepPath
): StepDraft | null {
  const parsed = parseStepStructurePath(path)
  if (parsed?.kind === 'top-step') {
    return drafts[parsed.topIndex] ?? null
  }
  if (parsed?.kind === 'branch-child') {
    const parent = drafts[parsed.topIndex]
    const branch = parent?.conditionalBranches.find(
      (item: ConditionalBranchDraft): boolean =>
        item.branchKey === parsed.branchKey
    )
    return branch?.steps[parsed.childIndex] ?? null
  }
  if (parsed?.kind === 'else-child') {
    return drafts[parsed.topIndex]?.elseSteps[parsed.childIndex] ?? null
  }
  return null
}

function getValidationErrors(
  path: EditableStepPath
): StepValidationErrors {
  const draft = resolveStepDraftAtPath(workingStepDrafts.value, path)
  return draft ? props.validateStepFn(draft) : {}
}

const graphPipeline = createStepGraphIncrementalPipeline()
const projectedGraph = shallowRef<StepGraph>({ nodes: [], edges: [] })
const canvasGraph = shallowRef<StepGraph>({ nodes: [], edges: [] })
let suppressDraftGraphRebuild = false
let suppressDisplayGraphRebuild = false

function getProjectionOptions(): StepGraphProjectionOptions {
  return {
    rootLabel: props.title,
    componentPreviews: props.componentPreviews,
    annotations: displayState.value.annotations
  }
}

function applyInjectedValidation(graph: StepGraph): void {
  graph.nodes.forEach((node: StepGraphNode): void => {
    if (node.editable && isEditableStepPath(node.path)) {
      node.errorCount = Object.keys(getValidationErrors(node.path)).length
    }
  })
}

function assignGraphResult(result: StepGraphIncrementalResult): void {
  applyInjectedValidation(result.projectedGraph)
  applyInjectedValidation(result.canvasGraph)
  projectedGraph.value = result.projectedGraph
  canvasGraph.value = result.canvasGraph
}

function rebuildGraphsFully(): void {
  try {
    assignGraphResult(
      graphPipeline.initialize(
        workingStepDrafts.value,
        getProjectionOptions(),
        displayState.value
      )
    )
    projectionError.value = ''
  } catch (error: unknown) {
    projectionError.value =
      error instanceof Error ? error.message : '步骤执行图无法生成。'
    assignGraphResult(
      graphPipeline.initialize(
        [],
        { rootLabel: props.title },
        displayState.value
      )
    )
  }
}

rebuildGraphsFully()

const validationErrors = computed(
  (): StepCanvasValidationError[] =>
    projectedGraph.value.nodes.flatMap(
      (node: StepGraphNode): StepCanvasValidationError[] => {
        if (
          !node.editable ||
          !isEditableStepPath(node.path) ||
          node.errorCount === 0
        ) {
          return []
        }
        return [
          {
            path: node.path,
            nodeLabel: node.label,
            messages: Object.values(getValidationErrors(node.path))
          }
        ]
      }
    )
)

const selectedNode = computed((): StepGraphNode | null => {
  if (!internalSelectedPath.value) {
    return null
  }
  return (
    projectedGraph.value.nodes.find(
      (node: StepGraphNode): boolean => node.path === internalSelectedPath.value
    ) ?? null
  )
})

const selectedStep = computed((): StepDraft | null => {
  const path = internalSelectedPath.value
  if (!path || !isEditableStepPath(path)) {
    return null
  }
  return resolveStepDraftAtPath(workingStepDrafts.value, path)
})

const selectedBranch = computed((): ConditionalBranchDraft | null => {
  const node = selectedNode.value
  const parentPath = node?.parentPath
    ? parseStepStructurePath(node.parentPath)
    : null
  if (node?.kind !== 'branch-lane' || parentPath?.kind !== 'top-step') {
    return null
  }
  return (
    workingStepDrafts.value[parentPath.topIndex]?.conditionalBranches[node.order] ??
    null
  )
})

const selectedElseStep = computed((): StepDraft | null => {
  const parsed = internalSelectedPath.value
    ? parseStepStructurePath(internalSelectedPath.value)
    : null
  if (parsed?.kind !== 'else') {
    return null
  }
  const parent = workingStepDrafts.value[parsed.topIndex]
  return parent?.type === 'conditional_branch' ? parent : null
})

const selectedDisplayState = computed(
  (): StepGraphNodeDisplayState =>
    internalSelectedPath.value
      ? displayState.value.nodeStates[internalSelectedPath.value] ?? {}
      : {}
)

const editableNodes = computed(
  (): StepGraphNode[] =>
    projectedGraph.value.nodes.filter(
      (node: StepGraphNode): boolean => node.editable
    )
)

const flowNodes = computed((): Array<Node<StepCanvasNodeData>> =>
  canvasGraph.value.nodes.map(
    (node: StepGraphNode): Node<StepCanvasNodeData> => ({
      id: node.path,
      label: node.label,
      position: { ...node.position },
      type: resolveNodeType(node),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      draggable: node.editable,
      selectable: true,
      connectable: false,
      focusable: false,
      deletable: false,
      width: node.width,
      height: node.height,
      class: [
        'step-canvas-flow-node',
        `is-${node.kind}`,
        node.readOnly ? 'is-read-only' : ''
      ],
      style: {
        width: `${node.width}px`,
        height: `${node.height}px`,
        padding: '0',
        border: '0',
        background: 'transparent'
      },
      data: {
        graphNode: node,
        palette: resolveNodePalette(node),
        shape: displayState.value.nodeStates[node.path]?.shape ?? 'rectangle',
        collapsed: displayState.value.nodeStates[node.path]?.collapsed === true,
        canCollapse: projectedGraph.value.nodes.some(
          (candidate: StepGraphNode): boolean => candidate.parentPath === node.path
        ),
        onToggleCollapse: toggleNodeCollapse,
        onAddAfter: handleRequestCreateAfter,
        onDuplicate: handleDuplicateNode,
        onMore: handleNodeAction,
        onOpenInspector: openNodeInspector,
        onOpenComponent: handleOpenComponent
      },
      ariaLabel: `${node.typeLabel}，${node.label}，${node.summary}`
    })
  )
)

const showEdgeLabels = computed((): boolean =>
  shouldShowStepGraphEdgeLabels(viewport.value.zoom)
)

function describeGraphEdge(edge: StepGraphEdge): string {
  const nodeByPath = new Map(
    canvasGraph.value.nodes.map(
      (node: StepGraphNode): [StepStructurePath, StepGraphNode] => [
        node.path,
        node
      ]
    )
  )
  const sourceLabel = nodeByPath.get(edge.source)?.label ?? edge.source
  const targetLabel = nodeByPath.get(edge.target)?.label ?? edge.target
  const relationLabel: Record<StepGraphEdge['kind'], string> = {
    sequence: '顺序执行关系',
    condition: '条件命中关系',
    else: '默认分支关系',
    component: '组件只读预览引用关系',
    'dependency-annotation': '依赖标注关系，仅作说明，不改变执行顺序',
    'parallel-annotation': '并行标注关系，仅作说明，不改变执行顺序'
  }
  return `${relationLabel[edge.kind]}：从“${sourceLabel}”到“${targetLabel}”，${edge.label}`
}

const flowEdges = computed((): Array<Edge<StepCanvasEdgeData>> =>
  canvasGraph.value.edges.map(
    (edge: StepGraphEdge): Edge<StepCanvasEdgeData> => {
      const visual = getStepGraphEdgeVisual(edge.kind)
      const title = describeGraphEdge(edge)
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'step-canvas-edge',
        markerEnd:
          visual.arrow === 'none'
            ? undefined
            : {
                type:
                  visual.arrow === 'closed'
                    ? MarkerType.ArrowClosed
                    : MarkerType.Arrow,
                color: visual.color,
                width: 14,
                height: 14
              },
        selectable: false,
        focusable: false,
        deletable: false,
        data: {
          graphEdge: edge,
          visual,
          connectionStyle: displayState.value.connectionStyle,
          showLabel: showEdgeLabels.value,
          title
        },
        ariaLabel: title
      }
    }
  )
)

const workspaceGridStyle = computed((): CSSProperties => {
  if (viewportMode.value === 'compact') {
    return { gridTemplateColumns: 'minmax(0, 1fr)' }
  }
  const leftWidth = leftCollapsed.value ? 44 : 224
  const inspectorWidth = inspectorCollapsed.value
    ? 44
    : viewportMode.value === 'desktop'
      ? 320
      : 288
  return {
    gridTemplateColumns: `${leftWidth}px minmax(0, 1fr) ${inspectorWidth}px`
  }
})

const canvasStageStyle = computed(
  (): CSSProperties => ({
    backgroundColor:
      displayState.value.background.kind === 'solid'
        ? displayState.value.background.color ?? '#f8fafc'
        : '#f8fafc'
  })
)

const backgroundLayerStyle = computed((): CSSProperties => {
  const preference = displayState.value.background
  if (preference.kind !== 'image' || !backgroundImageUrl.value) {
    return {}
  }

  const fit = preference.imageFit ?? 'cover'
  const fixed = preference.imageFixed ?? true
  return {
    backgroundImage: `url("${backgroundImageUrl.value}")`,
    backgroundPosition: fixed ? 'center' : `${viewport.value.x}px ${viewport.value.y}px`,
    backgroundRepeat: fit === 'repeat' ? 'repeat' : 'no-repeat',
    backgroundSize: fit === 'repeat' ? 'auto' : fit,
    opacity: preference.imageOpacity ?? 0.65
  }
})

const stepCount = computed(
  (): number =>
    projectedGraph.value.nodes.filter(
      (node: StepGraphNode): boolean =>
        node.kind === 'top-step' || node.kind === 'branch-step'
    ).length
)

const branchCount = computed(
  (): number =>
    projectedGraph.value.nodes.filter(
      (node: StepGraphNode): boolean =>
        node.kind === 'branch-lane' || node.kind === 'else-lane'
    ).length
)

const componentCount = computed(
  (): number =>
    projectedGraph.value.nodes.filter(
      (node: StepGraphNode): boolean =>
        node.kind === 'top-step' && node.stepType === 'component_call'
    ).length
)
const referencedComponentIds = computed(
  (): number[] => [
    ...new Set(
      workingStepDrafts.value.flatMap(
        (step: StepDraft): number[] =>
          step.type === 'component_call' && step.componentId !== null
            ? [step.componentId]
            : []
      )
    )
  ]
)

const resolvedErrorCount = computed(
  (): number =>
    Math.max(
      props.errorCount,
      validationErrors.value.reduce(
        (total: number, error: StepCanvasValidationError): number =>
          total + error.messages.length,
        0
      )
    )
)

const zoomPercent = computed((): number => Math.round(viewport.value.zoom * 100))

const resolvedStatusMessage = computed(
  (): string =>
    projectionError.value ||
    preferenceError.value ||
    props.statusMessage ||
    commandStatusMessage.value ||
    (viewportReady.value ? '' : '画布视口正在初始化，请稍候。')
)

function resolveNodeType(node: StepGraphNode): string {
  if (node.kind === 'root') {
    return 'root-node'
  }
  if (node.kind === 'branch-lane' || node.kind === 'else-lane') {
    return 'branch-lane-node'
  }
  if (node.kind === 'component-preview') {
    return 'component-preview-node'
  }
  if (node.stepType === 'conditional_branch') {
    return 'conditional-node'
  }
  if (node.stepType === 'component_call') {
    return 'component-call-node'
  }
  return 'step-node'
}

function resolveNodePalette(node: StepGraphNode): { background: string; border: string } {
  const customColor = displayState.value.nodeStates[node.path]?.color
  if (customColor) {
    return { background: '#ffffff', border: customColor }
  }
  if (node.kind === 'root') {
    return { background: '#f8fafc', border: '#64748b' }
  }
  if (node.kind === 'branch-lane' || node.kind === 'else-lane') {
    return { background: '#fffbeb', border: '#d97706' }
  }
  if (node.stepType === 'template_assert' || node.stepType === 'ocr_assert') {
    return { background: '#f0fdf4', border: '#16a34a' }
  }
  if (node.stepType === 'conditional_branch' || node.stepType === 'wait') {
    return { background: '#fffbeb', border: '#d97706' }
  }
  if (node.stepType === 'component_call' || node.kind === 'component-preview') {
    return { background: '#eef2ff', border: '#4f46e5' }
  }
  return { background: '#eff6ff', border: '#2563eb' }
}

function setSelectedPath(path: StepStructurePath | null): void {
  internalSelectedPath.value = path
  const graphNode = path
    ? projectedGraph.value.nodes.find(
        (node: StepGraphNode): boolean => node.path === path
      )
    : null
  const parentPath = graphNode?.parentPath
    ? parseStepStructurePath(graphNode.parentPath)
    : null
  if (graphNode?.kind === 'branch-lane' && parentPath?.kind === 'top-step') {
    selectedBranchDraftId.value =
      workingStepDrafts.value[parentPath.topIndex]?.conditionalBranches[
        graphNode.order
      ]?.id ?? null
  } else {
    selectedBranchDraftId.value = null
  }
  emit('update:selectedPath', path)
  emit('select-node', path)
}

function selectOnly(path: StepStructurePath | null): void {
  selectedPaths.value = new Set(path ? [path] : [])
  setSelectedPath(path)
  void nextTick().then(syncFlowSelection)
}

function syncFlowSelection(): void {
  if (!flowStore.value) {
    return
  }
  const targetPaths = [...selectedPaths.value]
  syncingFlowSelection.value = true
  try {
    flowStore.value.removeSelectedElements()
    const nodes = targetPaths.flatMap((path: StepStructurePath) => {
      const node = flowStore.value?.findNode(path)
      return node ? [node] : []
    })
    if (nodes.length > 0) {
      flowStore.value.addSelectedNodes(nodes)
    }
  } finally {
    syncingFlowSelection.value = false
  }
}

async function focusNode(path: StepStructurePath): Promise<void> {
  await nextTick()
  const store = viewportReady.value ? flowStore.value : null
  const node = store?.findNode(path)
  if (!node || !store) {
    return
  }
  const width = node.dimensions.width || Number(node.width) || 224
  const height = node.dimensions.height || Number(node.height) || 96
  await store.setCenter(
    node.computedPosition.x + width / 2,
    node.computedPosition.y + height / 2,
    {
      zoom: Math.max(viewport.value.zoom, 0.8),
      duration: prefersReducedMotion.value ? 0 : 180
    }
  )
  await nextTick()
  const nodeContainer = Array.from(
    document.querySelectorAll<HTMLElement>('[data-id]')
  ).find((element: HTMLElement): boolean => element.dataset.id === path)
  const focusTarget =
    nodeContainer?.querySelector<HTMLElement>('.step-execution-node') ??
    nodeContainer
  focusTarget?.focus({ preventScroll: true })
}

function handleNodeClick(event: NodeMouseEvent): void {
  const parsed = parseStepStructurePath(event.node.id)
  if (!parsed) {
    return
  }
  const path = event.node.id as StepStructurePath
  const pointerEvent = event.event as MouseEvent
  if (pointerEvent.metaKey || pointerEvent.ctrlKey || pointerEvent.shiftKey) {
    const nextSelectedPaths = new Set(selectedPaths.value)
    if (nextSelectedPaths.has(path)) {
      nextSelectedPaths.delete(path)
    } else {
      nextSelectedPaths.add(path)
    }
    selectedPaths.value = nextSelectedPaths
    setSelectedPath(nextSelectedPaths.has(path) ? path : nextSelectedPaths.values().next().value ?? null)
    return
  }
  selectOnly(path)
}

function handleNodesChange(changes: NodeChange[]): void {
  if (syncingFlowSelection.value) {
    return
  }
  const selectionChanges = changes.filter(
    (change: NodeChange): boolean => change.type === 'select'
  )
  if (selectionChanges.length === 0) {
    return
  }
  const nextSelectedPaths = new Set(selectedPaths.value)
  let lastSelectedPath: StepStructurePath | null = null
  selectionChanges.forEach((change: NodeChange): void => {
    if (change.type !== 'select' || !parseStepStructurePath(change.id)) {
      return
    }
    const path = change.id as StepStructurePath
    if (change.selected) {
      nextSelectedPaths.add(path)
      lastSelectedPath = path
    } else {
      nextSelectedPaths.delete(path)
    }
  })
  selectedPaths.value = nextSelectedPaths
  if (lastSelectedPath) {
    setSelectedPath(lastSelectedPath)
  } else if (
    internalSelectedPath.value &&
    !nextSelectedPaths.has(internalSelectedPath.value)
  ) {
    setSelectedPath(nextSelectedPaths.values().next().value ?? null)
  }
}

function handleSidebarSelect(path: StepStructurePath): void {
  selectOnly(path)
  mobileLibraryOpen.value = false
  void focusNode(path)
}

function openNodeInspector(path: StepStructurePath): void {
  selectOnly(path)
  inspectorTab.value = 'config'
  if (viewportMode.value === 'compact') {
    mobileInspectorOpen.value = true
  } else {
    inspectorCollapsed.value = false
  }
  void nextTick().then((): void => {
    const firstControl = document.querySelector<HTMLElement>(
      [
        '.step-canvas-inspector:not(.is-collapsed) input:not([disabled])',
        '.step-canvas-inspector:not(.is-collapsed) textarea:not([disabled])',
        '.step-canvas-inspector:not(.is-collapsed) button:not([disabled])',
        '.step-canvas-mobile-inspector input:not([disabled])',
        '.step-canvas-mobile-inspector textarea:not([disabled])',
        '.step-canvas-mobile-inspector button:not([disabled])'
      ].join(', ')
    )
    firstControl?.focus({ preventScroll: true })
  })
}

function handleOpenComponent(componentId: number): void {
  emit('open-component', componentId)
}

function handleRequestCreateAfter(path: EditableStepPath): void {
  selectOnly(path)
  emit('request-create-after', path)
  createStepAtSelection('wait', path)
}

function handleNodeAction(path: EditableStepPath): void {
  selectOnly(path)
  inspectorTab.value = 'config'
  if (viewportMode.value === 'compact') {
    mobileInspectorOpen.value = true
  }
  emit('node-action', path)
}

function toggleNodeCollapse(path: StepStructurePath): void {
  const currentNodeState = displayState.value.nodeStates[path] ?? {}
  editor.commitDisplayState({
    ...displayState.value,
    nodeStates: {
      ...displayState.value.nodeStates,
      [path]: {
        ...currentNodeState,
        collapsed: currentNodeState.collapsed !== true
      }
    }
  })
}

function handleConnectionStyleChange(
  connectionStyle: StepGraphDisplayState['connectionStyle']
): void {
  editor.commitDisplayState({
    ...displayState.value,
    connectionStyle
  })
}

function commitStepMutation(
  result: StepGraphMutationResult<StepDraft>,
  change: Omit<StepCanvasStepsChange, 'focusPath'>
): void {
  const migratedDisplayState = migrateStepGraphDisplayState(
    displayState.value,
    result.pathMigration
  )
  suppressDraftGraphRebuild = true
  suppressDisplayGraphRebuild = true
  editor.commitSnapshot(result.drafts, migratedDisplayState)
  try {
    assignGraphResult(
      graphPipeline.updateStructure(
        result.drafts,
        result.pathMigration,
        getProjectionOptions(),
        migratedDisplayState
      )
    )
    projectionError.value = ''
  } catch (error: unknown) {
    projectionError.value =
      error instanceof Error ? error.message : '步骤执行图增量更新失败。'
    rebuildGraphsFully()
  }
  selectedPaths.value = new Set(result.focusPath ? [result.focusPath] : [])
  setSelectedPath(result.focusPath)
  emit('steps-change', result.drafts, {
    ...change,
    focusPath: result.focusPath
  })
  const commandLabels: Record<StepCanvasStepsChange['kind'], string> = {
    create: '新增',
    move: '移动',
    reorder: '排序',
    duplicate: '重复创建',
    delete: '删除',
    paste: '粘贴',
    cut: '剪切'
  }
  commandStatusMessage.value = `已完成${commandLabels[change.kind]}，步骤结构已更新。`
  if (result.focusPath) {
    void nextTick().then((): Promise<void> => focusNode(result.focusPath as EditableStepPath))
  }
}

function reportCommandError(
  error: unknown,
  fallbackMessage: string,
  path: EditableStepPath | null = null
): void {
  const message = error instanceof Error ? error.message : fallbackMessage
  ElMessage.warning(message)
  emit('error', { message, path, source: 'command' })
}

function getSelectedEditablePaths(): EditableStepPath[] {
  return [...selectedPaths.value].filter(isEditableStepPath)
}

function resolveInsertionTarget(
  path: StepStructurePath | null = internalSelectedPath.value
): { containerPath: StepContainerPath; index: number } {
  const parsed = path ? parseStepStructurePath(path) : null
  if (parsed?.kind === 'top-step') {
    return { containerPath: 'root', index: parsed.topIndex + 1 }
  }
  if (parsed?.kind === 'branch-child') {
    const containerPath = getStepContainerPath(path as EditableStepPath)
    return { containerPath, index: parsed.childIndex + 1 }
  }
  if (parsed?.kind === 'else-child') {
    const containerPath = getStepContainerPath(path as EditableStepPath)
    return { containerPath, index: parsed.childIndex + 1 }
  }
  if (parsed?.kind === 'branch' || parsed?.kind === 'else') {
    const containerPath = path as StepContainerPath
    return {
      containerPath,
      index: getStepContainerLength(workingStepDrafts.value, containerPath)
    }
  }
  if (parsed?.kind === 'component-preview') {
    return { containerPath: 'root', index: parsed.topIndex + 1 }
  }
  return {
    containerPath: 'root',
    index: workingStepDrafts.value.length
  }
}

function createStepAtSelection(
  stepType: StepType,
  selectedPath: StepStructurePath | null = internalSelectedPath.value
): void {
  const target = resolveInsertionTarget(selectedPath)
  createStepAtTarget(stepType, target.containerPath, target.index)
}

function createStepAtTarget(
  stepType: StepType,
  containerPath: StepContainerPath,
  insertionIndex: number
): void {
  try {
    const draft = createEmptyStepDraft(insertionIndex)
    Object.assign(draft, normalizeStepByType(draft, stepType))
    const result = insertStepDraft(
      workingStepDrafts.value,
      containerPath,
      insertionIndex,
      regenerateStepDraftTemporaryIds(draft)
    )
    commitStepMutation(result, {
      kind: 'create',
      sourcePath: result.focusPath as EditableStepPath,
      targetContainerPath: containerPath,
      insertionIndex
    })
  } catch (error: unknown) {
    reportCommandError(error, '新增步骤失败。')
  }
}

function handleCreateStep(stepType: StepType): void {
  createStepAtSelection(stepType)
  emit('create-step', stepType)
}

function copySelected(
  source: StepCanvasClipboard['source'] = 'copy',
  announce = true
): boolean {
  try {
    clipboard.value = copyStepDraftSelection(
      workingStepDrafts.value,
      getSelectedEditablePaths(),
      source
    )
    if (announce) {
      ElMessage.success(`已复制 ${clipboard.value.entries.length} 个步骤。`)
    }
    return true
  } catch (error: unknown) {
    reportCommandError(error, '复制步骤失败。')
    return false
  }
}

function countAffectedNodes(paths: readonly EditableStepPath[]): number {
  const selected = new Set(paths)
  return projectedGraph.value.nodes.filter(
    (node: StepGraphNode): boolean => {
      if (selected.has(node.path as EditableStepPath)) {
        return true
      }
      let parentPath = node.parentPath
      while (parentPath) {
        if (selected.has(parentPath as EditableStepPath)) {
          return true
        }
        parentPath =
          projectedGraph.value.nodes.find(
            (candidate: StepGraphNode): boolean => candidate.path === parentPath
          )?.parentPath ?? null
      }
      return false
    }
  ).length
}

async function deleteSelected(kind: 'delete' | 'cut' = 'delete'): Promise<boolean> {
  const paths = getSelectedEditablePaths()
  if (paths.length === 0) {
    reportCommandError(new Error('请先选择可编辑步骤。'), '删除步骤失败。')
    return false
  }

  const affectedCount = countAffectedNodes(paths)
  if (paths.length > 1 || affectedCount > paths.length) {
    try {
      await ElMessageBox.confirm(
        `该操作会移除 ${affectedCount} 个节点（含子树），是否继续？`,
        kind === 'cut' ? '确认剪切' : '确认删除',
        {
          type: 'warning',
          confirmButtonText: kind === 'cut' ? '剪切' : '删除',
          cancelButtonText: '取消'
        }
      )
    } catch {
      return false
    }
  }

  try {
    const sourcePath = paths[0]
    const result = deleteStepDraftSelection(workingStepDrafts.value, paths)
    commitStepMutation(result, {
      kind,
      sourcePath,
      targetContainerPath: getStepContainerPath(sourcePath)
    })
    return true
  } catch (error: unknown) {
    reportCommandError(error, '删除步骤失败。')
    return false
  }
}

async function cutSelected(): Promise<void> {
  const previousClipboard = clipboard.value
  if (!copySelected('cut', false)) {
    return
  }
  if (!await deleteSelected('cut')) {
    clipboard.value = previousClipboard
    return
  }
  ElMessage.success(`已剪切 ${clipboard.value?.entries.length ?? 0} 个步骤。`)
}

function pasteSelected(
  sourceClipboard: StepCanvasClipboard | null = clipboard.value,
  changeKind: 'paste' | 'duplicate' = 'paste'
): void {
  if (!sourceClipboard) {
    reportCommandError(new Error('剪贴板中没有可粘贴的步骤。'), '粘贴步骤失败。')
    return
  }
  try {
    const target = resolveInsertionTarget()
    const result = pasteStepDraftClipboard(
      workingStepDrafts.value,
      sourceClipboard,
      target.containerPath,
      target.index
    )
    commitStepMutation(result, {
      kind: changeKind,
      sourcePath: sourceClipboard.entries[0].sourcePath,
      targetContainerPath: target.containerPath,
      insertionIndex: target.index
    })
  } catch (error: unknown) {
    reportCommandError(error, '粘贴步骤失败。')
  }
}

function duplicateSelected(): void {
  try {
    const copied = copyStepDraftSelection(
      workingStepDrafts.value,
      getSelectedEditablePaths()
    )
    pasteSelected(copied, 'duplicate')
  } catch (error: unknown) {
    reportCommandError(error, '重复步骤失败。')
  }
}

function handleDuplicateNode(path: EditableStepPath): void {
  selectOnly(path)
  duplicateSelected()
}

function handleInspectorCommand(command: StepCanvasInspectorCommand): void {
  if (command === 'copy') {
    copySelected()
  } else if (command === 'cut') {
    void cutSelected()
  } else if (command === 'paste') {
    pasteSelected()
  } else if (command === 'duplicate') {
    duplicateSelected()
  } else {
    void deleteSelected()
  }
}

function handleNodeDragStart(event: NodeDragEvent): void {
  if (!isEditableStepPath(event.node.id)) {
    return
  }
  const graphNode = canvasGraph.value.nodes.find(
    (node: StepGraphNode): boolean => node.path === event.node.id
  )
  if (!graphNode) {
    return
  }
  dragOrigin.value = {
    path: event.node.id,
    position: { ...graphNode.position }
  }
  dropCandidate.value = null
}

function handleNodeDrag(event: NodeDragEvent): void {
  if (!isEditableStepPath(event.node.id)) {
    dropCandidate.value = null
    return
  }
  dropCandidate.value = findDropCandidate(event)
}

function findDropCandidate(event: NodeDragEvent): StepCanvasDropCandidate | null {
  const sourcePath = event.node.id
  if (!isEditableStepPath(sourcePath)) {
    return null
  }
  const width = event.node.dimensions.width || Number(event.node.width) || 224
  const height = event.node.dimensions.height || Number(event.node.height) || 96
  const center = {
    x: event.node.position.x + width / 2,
    y: event.node.position.y + height / 2
  }
  const target = findNearestDropNode(center, sourcePath)
  if (!target) {
    return null
  }
  const resolvedTarget = resolveDropTarget(target, center)
  if (!resolvedTarget) {
    return null
  }
  if (resolvedTarget.readOnly) {
    return {
      mode: 'move',
      targetContainerPath: getStepContainerPath(sourcePath),
      insertionIndex: 0,
      x: target.position.x - 8,
      y: target.position.y - 12,
      width: target.width + 16,
      valid: false,
      reason: '组件预览为只读区域，不能放置步骤。'
    }
  }
  const assessment = assessStepDraftDrop(
    workingStepDrafts.value,
    sourcePath,
    resolvedTarget.targetContainerPath,
    resolvedTarget.insertionIndex
  )
  return {
    mode: 'move',
    targetContainerPath: resolvedTarget.targetContainerPath,
    insertionIndex: resolvedTarget.insertionIndex,
    x: target.position.x - 8,
    y: resolvedTarget.indicatorY,
    width: target.width + 16,
    valid: assessment.valid,
    reason: assessment.reason
  }
}

function findNearestDropNode(
  center: StepGraphPosition,
  excludedPath: StepStructurePath | null = null
): StepGraphNode | null {
  const candidates = canvasGraph.value.nodes
    .filter(
      (node: StepGraphNode): boolean =>
        excludedPath === null || node.path !== excludedPath
    )
    .map((node: StepGraphNode): { node: StepGraphNode; distance: number } => {
      const distanceX = Math.max(
        node.position.x - center.x,
        0,
        center.x - (node.position.x + node.width)
      )
      const distanceY = Math.max(
        node.position.y - center.y,
        0,
        center.y - (node.position.y + node.height)
      )
      return {
        node,
        distance: Math.hypot(distanceX, distanceY)
      }
    })
    .filter(
      (candidate: { node: StepGraphNode; distance: number }): boolean =>
        candidate.distance <= 96
    )
    .sort(
      (
        left: { node: StepGraphNode; distance: number },
        right: { node: StepGraphNode; distance: number }
      ): number => left.distance - right.distance
    )

  return candidates[0]?.node ?? null
}

function resolveDropTarget(
  target: StepGraphNode,
  center: StepGraphPosition
): {
  targetContainerPath: StepContainerPath
  insertionIndex: number
  indicatorY: number
  readOnly: boolean
} | null {
  if (target.kind === 'component-preview') {
    return {
      targetContainerPath: 'root',
      insertionIndex: 0,
      indicatorY: target.position.y - 12,
      readOnly: true
    }
  }

  let targetContainerPath: StepContainerPath
  let insertionIndex: number
  let indicatorY: number
  if (target.kind === 'root') {
    targetContainerPath = 'root'
    insertionIndex = 0
    indicatorY = target.position.y + target.height + 16
  } else if (target.kind === 'branch-lane' || target.kind === 'else-lane') {
    targetContainerPath = target.path as StepContainerPath
    insertionIndex = 0
    indicatorY = target.position.y + target.height + 16
  } else if (isEditableStepPath(target.path)) {
    const insertAfter = center.y >= target.position.y + target.height / 2
    targetContainerPath = getStepContainerPath(target.path)
    insertionIndex = target.order + (insertAfter ? 1 : 0)
    indicatorY = insertAfter
      ? target.position.y + target.height + 12
      : target.position.y - 12
  } else {
    return null
  }
  return {
    targetContainerPath,
    insertionIndex,
    indicatorY,
    readOnly: false
  }
}

const paletteStepTypes: readonly StepType[] = [
  'wait',
  'click',
  'input',
  'select_option',
  'template_assert',
  'ocr_assert',
  'component_call',
  'navigate',
  'scroll',
  'long_press',
  'conditional_branch'
]

function parsePaletteDragType(event: DragEvent): StepType | null {
  if (paletteDragType.value) {
    return paletteDragType.value
  }
  const serialized = event.dataTransfer?.getData(STEP_CANVAS_PALETTE_MIME)
  if (!serialized) {
    return null
  }
  try {
    const payload = JSON.parse(serialized) as StepCanvasPaletteDragPayload
    return paletteStepTypes.includes(payload.stepType)
      ? payload.stepType
      : null
  } catch {
    return null
  }
}

function createPaletteDraft(stepType: StepType, stepNo: number): StepDraft {
  const draft = createEmptyStepDraft(stepNo)
  Object.assign(draft, normalizeStepByType(draft, stepType))
  return draft
}

function findPaletteDropCandidate(
  event: DragEvent,
  stepType: StepType
): StepCanvasDropCandidate | null {
  const store = flowStore.value
  if (!store) {
    return null
  }
  const center = store.screenToFlowCoordinate({
    x: event.clientX,
    y: event.clientY
  })
  const target = findNearestDropNode(center)
  if (!target) {
    const topNodes = canvasGraph.value.nodes.filter(
      (node: StepGraphNode): boolean => node.kind === 'top-step'
    )
    const anchor = topNodes.at(-1) ?? canvasGraph.value.nodes[0]
    if (!anchor) {
      return null
    }
    const insertionIndex = workingStepDrafts.value.length
    const assessment = assessStepDraftInsertion(
      workingStepDrafts.value,
      createPaletteDraft(stepType, insertionIndex),
      'root',
      insertionIndex
    )
    return {
      mode: 'create',
      targetContainerPath: 'root',
      insertionIndex,
      x: anchor.position.x - 8,
      y: anchor.position.y + anchor.height + 12,
      width: anchor.width + 16,
      valid: assessment.valid,
      reason: assessment.reason
    }
  }

  const resolvedTarget = resolveDropTarget(target, center)
  if (!resolvedTarget) {
    return null
  }
  if (resolvedTarget.readOnly) {
    return {
      mode: 'create',
      targetContainerPath: 'root',
      insertionIndex: workingStepDrafts.value.length,
      x: target.position.x - 8,
      y: target.position.y - 12,
      width: target.width + 16,
      valid: false,
      reason: '组件预览为只读区域，不能放置步骤。'
    }
  }
  const assessment = assessStepDraftInsertion(
    workingStepDrafts.value,
    createPaletteDraft(stepType, resolvedTarget.insertionIndex),
    resolvedTarget.targetContainerPath,
    resolvedTarget.insertionIndex
  )
  return {
    mode: 'create',
    targetContainerPath: resolvedTarget.targetContainerPath,
    insertionIndex: resolvedTarget.insertionIndex,
    x: target.position.x - 8,
    y: resolvedTarget.indicatorY,
    width: target.width + 16,
    valid: assessment.valid,
    reason: assessment.reason
  }
}

function handlePaletteDragStart(stepType: StepType): void {
  paletteDragType.value = stepType
}

function handlePaletteDragEnd(): void {
  paletteDragType.value = null
  if (dropCandidate.value?.mode === 'create') {
    dropCandidate.value = null
  }
}

function handlePaletteDragOver(event: DragEvent): void {
  const stepType = parsePaletteDragType(event)
  if (!stepType || !viewportReady.value) {
    return
  }
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
  dropCandidate.value = findPaletteDropCandidate(event, stepType)
}

function handlePaletteDragLeave(event: DragEvent): void {
  const currentTarget = event.currentTarget
  if (
    currentTarget instanceof Element &&
    event.relatedTarget instanceof Node &&
    currentTarget.contains(event.relatedTarget)
  ) {
    return
  }
  if (dropCandidate.value?.mode === 'create') {
    dropCandidate.value = null
  }
}

function handlePaletteDrop(event: DragEvent): void {
  const stepType = parsePaletteDragType(event)
  const candidate = dropCandidate.value?.mode === 'create'
    ? dropCandidate.value
    : stepType
      ? findPaletteDropCandidate(event, stepType)
      : null
  paletteDragType.value = null
  dropCandidate.value = null
  if (!stepType || !candidate) {
    return
  }
  event.preventDefault()
  if (!candidate.valid) {
    reportCommandError(new Error(candidate.reason), '新增步骤失败。')
    return
  }
  createStepAtTarget(
    stepType,
    candidate.targetContainerPath,
    candidate.insertionIndex
  )
  emit('create-step', stepType)
}

function restoreDraggedNode(): void {
  if (!dragOrigin.value || !flowStore.value) {
    return
  }
  flowStore.value.updateNode(dragOrigin.value.path, {
    position: { ...dragOrigin.value.position }
  })
}

function handleNodeDragStop(event: NodeDragEvent): void {
  if (!isEditableStepPath(event.node.id)) {
    dropCandidate.value = null
    dragOrigin.value = null
    return
  }
  const path = event.node.id
  const candidate = dropCandidate.value
  if (candidate) {
    if (!candidate.valid) {
      restoreDraggedNode()
      ElMessage.warning(candidate.reason)
    } else {
      try {
        const result = moveStepDraftAtInsertion(
          workingStepDrafts.value,
          path,
          candidate.targetContainerPath,
          candidate.insertionIndex
        )
        if (result) {
          const assessment = assessStepDraftDrop(
            workingStepDrafts.value,
            path,
            candidate.targetContainerPath,
            candidate.insertionIndex
          )
          commitStepMutation(result, {
            kind: assessment.operation === 'reorder' ? 'reorder' : 'move',
            sourcePath: path,
            targetContainerPath: candidate.targetContainerPath,
            insertionIndex: candidate.insertionIndex
          })
        } else {
          restoreDraggedNode()
        }
      } catch (error: unknown) {
        restoreDraggedNode()
        ElMessage.warning(
          error instanceof Error ? error.message : '当前步骤不能放置到该位置。'
        )
      }
    }
    dropCandidate.value = null
    dragOrigin.value = null
    return
  }

  const position = {
    x: event.node.position.x,
    y: event.node.position.y
  }
  const currentNodeState = displayState.value.nodeStates[path] ?? {}
  editor.commitDisplayState({
    ...displayState.value,
    nodeStates: {
      ...displayState.value.nodeStates,
      [path]: {
        ...currentNodeState,
        position
      }
    }
  })
  emit('node-position-change', path, position)
  dropCandidate.value = null
  dragOrigin.value = null
}

function handleMove(event: StepCanvasMoveEvent): void {
  viewport.value = { ...event.flowTransform }
}

async function fitView(): Promise<void> {
  const store = viewportReady.value ? flowStore.value : null
  if (!store) {
    return
  }
  await store.fitView({
    padding: 0.15,
    maxZoom: 1.15,
    duration: prefersReducedMotion.value ? 0 : 180
  })
}

async function zoomIn(): Promise<void> {
  const store = viewportReady.value ? flowStore.value : null
  await store?.zoomIn({
    duration: prefersReducedMotion.value ? 0 : 180
  })
}

async function zoomOut(): Promise<void> {
  const store = viewportReady.value ? flowStore.value : null
  await store?.zoomOut({
    duration: prefersReducedMotion.value ? 0 : 180
  })
}

async function autoLayout(): Promise<void> {
  if (!viewportReady.value) {
    return
  }
  const dimensioned = applyStepGraphDisplayState(projectedGraph.value, displayState.value)
  const visibleGraph = filterCollapsedStepGraph(dimensioned, displayState.value)
  const laidOut = layoutStepGraph(visibleGraph)
  const nextNodeStates = { ...displayState.value.nodeStates }

  laidOut.nodes.forEach((node: StepGraphNode): void => {
    nextNodeStates[node.path] = {
      ...nextNodeStates[node.path],
      position: { ...node.position }
    }
  })

  editor.commitDisplayState({
    ...displayState.value,
    nodeStates: nextNodeStates
  })
  await nextTick()
  await fitView()
}

async function resetZoom(): Promise<void> {
  const store = viewportReady.value ? flowStore.value : null
  if (!store) {
    return
  }
  await store.zoomTo(1, {
    duration: prefersReducedMotion.value ? 0 : 180
  })
}

function applySelectedStyle(patch: StepGraphNodeDisplayState): void {
  const paths = getSelectedEditablePaths()
  if (paths.length === 0) {
    return
  }
  const nodeStates = { ...displayState.value.nodeStates }
  paths.forEach((path: EditableStepPath): void => {
    nodeStates[path] = {
      ...nodeStates[path],
      ...patch
    }
  })
  editor.commitDisplayState({
    ...displayState.value,
    nodeStates
  })
}

function resetSelectedStyle(): void {
  const paths = getSelectedEditablePaths()
  if (paths.length === 0) {
    return
  }
  const nodeStates = { ...displayState.value.nodeStates }
  paths.forEach((path: EditableStepPath): void => {
    const {
      color: _color,
      shape: _shape,
      size: _size,
      ...remainingState
    } = nodeStates[path] ?? {}
    nodeStates[path] = remainingState
  })
  editor.commitDisplayState({
    ...displayState.value,
    nodeStates
  })
}

function createAnnotation(value: {
  target: EditableStepPath
  kind: StepGraphAnnotationKind
  label: string
}): void {
  const source = internalSelectedPath.value
  if (!source || !isEditableStepPath(source) || source === value.target) {
    reportCommandError(
      new Error('说明性关系需要两个不同的可编辑步骤。'),
      '创建标注关系失败。'
    )
    return
  }
  const duplicate = displayState.value.annotations.some(
    (annotation: StepGraphAnnotation): boolean =>
      annotation.source === source &&
      annotation.target === value.target &&
      annotation.kind === value.kind
  )
  if (duplicate) {
    reportCommandError(
      new Error('相同类型和方向的标注关系已存在。'),
      '创建标注关系失败。'
    )
    return
  }
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `annotation-${Date.now()}-${displayState.value.annotations.length + 1}`
  editor.commitDisplayState({
    ...displayState.value,
    annotations: [
      ...displayState.value.annotations,
      {
        id,
        source,
        target: value.target,
        kind: value.kind,
        ...(value.label.trim() ? { label: value.label.trim() } : {})
      }
    ]
  })
}

function deleteAnnotation(id: string): void {
  editor.commitDisplayState({
    ...displayState.value,
    annotations: displayState.value.annotations.filter(
      (annotation: StepGraphAnnotation): boolean => annotation.id !== id
    )
  })
}

function updateSelectedStepType(nextType: StepType): void {
  if (!selectedStep.value) {
    return
  }
  Object.assign(
    selectedStep.value,
    normalizeStepByType(selectedStep.value, nextType)
  )
}

function updateChildStepType(step: StepDraft, nextType: StepType): void {
  Object.assign(step, normalizeStepByType(step, nextType))
}

function updateSelectedBranchKey(nextBranchKey: string): void {
  const node = selectedNode.value
  const parentPath = node?.parentPath
    ? parseStepStructurePath(node.parentPath)
    : null
  if (
    node?.kind !== 'branch-lane' ||
    parentPath?.kind !== 'top-step' ||
    !selectedBranch.value
  ) {
    return
  }
  const branchId = selectedBranch.value.id

  const nextDrafts = JSON.parse(
    JSON.stringify(workingStepDrafts.value)
  ) as StepDraft[]
  const nextBranch =
    nextDrafts[parentPath.topIndex]?.conditionalBranches[node.order]
  if (!nextBranch) {
    return
  }
  nextBranch.branchKey = nextBranchKey
  const nextGraph = projectStepDraftsToGraph(nextDrafts, {
    rootLabel: props.title,
    componentPreviews: props.componentPreviews
  })
  const nextPath = nextGraph.nodes.find(
    (candidate: StepGraphNode): boolean =>
      candidate.kind === 'branch-lane' &&
      candidate.parentPath === node.parentPath &&
      candidate.order === node.order
  )?.path
  if (!nextPath) {
    return
  }

  const oldPath = node.path
  const migratePath = (path: string): string =>
    path === oldPath || path.startsWith(`${oldPath}:child:`)
      ? `${nextPath}${path.slice(oldPath.length)}`
      : path
  const nodeStates = Object.fromEntries(
    Object.entries(displayState.value.nodeStates).map(
      ([path, state]): [string, StepGraphNodeDisplayState] => [
        migratePath(path),
        state
      ]
    )
  )
  const annotations = displayState.value.annotations.map(
    (annotation: StepGraphAnnotation): StepGraphAnnotation => {
    const source = migratePath(annotation.source)
    const target = migratePath(annotation.target)
    return {
      ...annotation,
      source: isEditableStepPath(source) ? source : annotation.source,
      target: isEditableStepPath(target) ? target : annotation.target
    }
    }
  )
  editor.commitSnapshot(
    nextDrafts,
    {
      ...displayState.value,
      nodeStates,
      annotations
    },
    true
  )
  selectedBranchDraftId.value = branchId
  selectOnly(nextPath)
}

function getStepTemplateOptions(step: StepDraft): StepTemplateOption[] {
  if (props.getStepTemplateOptionsFn) {
    return props.getStepTemplateOptionsFn(step)
  }
  const usesVisualLocator =
    (
      step.type === 'click' ||
      step.type === 'input' ||
      step.type === 'scroll' ||
      step.type === 'long_press'
    ) && step.locator === 'visual'
  if (
    step.type !== 'template_assert' &&
    step.type !== 'ocr_assert' &&
    !usesVisualLocator
  ) {
    return []
  }

  const expectedStrategy = step.type === 'ocr_assert' ? 'ocr' : 'template'
  const currentTemplateId = usesVisualLocator
    ? step.visualTemplateId
    : step.templateId
  const options = props.templates
    .filter(
      (template: Template): boolean =>
        template.matchStrategy === expectedStrategy
    )
    .map(
      (template: Template): StepTemplateOption => ({
        id: template.id,
        label: formatTemplateOptionLabel(template)
      })
    )

  if (
    currentTemplateId !== null &&
    !options.some(
      (option: StepTemplateOption): boolean => option.id === currentTemplateId
    )
  ) {
    const currentTemplate = props.templates.find(
      (template: Template): boolean => template.id === currentTemplateId
    )
    if (currentTemplate) {
      options.unshift({
        id: currentTemplate.id,
        label: `${formatTemplateOptionLabel(currentTemplate)} · 当前值不符合 ${expectedStrategy} 策略`
      })
    }
  }
  return options
}

function formatTemplateOptionLabel(template: Template): string {
  const baselineLabel =
    template.currentBaselineRevisionId === null
      ? '无当前基准'
      : `当前基准 ${template.baselineVersion}`
  return `${template.name} (#${template.id}) · ${template.status} · ${baselineLabel}`
}

function getStepTemplateHint(step: StepDraft): string {
  if (props.getStepTemplateHintFn) {
    return props.getStepTemplateHintFn(step)
  }
  const usesVisualLocator =
    (
      step.type === 'click' ||
      step.type === 'input' ||
      step.type === 'scroll' ||
      step.type === 'long_press'
    ) && step.locator === 'visual'
  const currentTemplateId = usesVisualLocator
    ? step.visualTemplateId
    : step.templateId
  if (currentTemplateId === null) {
    return ''
  }

  const template = props.templates.find(
    (item: Template): boolean => item.id === currentTemplateId
  )
  if (!template) {
    return '当前模板不存在，请重新选择。'
  }

  const messages: string[] = []
  if (
    (step.type === 'template_assert' || usesVisualLocator) &&
    template.matchStrategy !== 'template'
  ) {
    messages.push('当前模板不是 template 策略。')
  }
  if (step.type === 'ocr_assert' && template.matchStrategy !== 'ocr') {
    messages.push('当前模板不是 ocr 策略。')
  }
  if (template.currentBaselineRevisionId === null) {
    messages.push('当前模板缺少当前基准版本。')
  }
  if (template.status !== 'published') {
    messages.push('当前模板未发布。')
  }
  return messages.join(' ')
}

function formatComponentOptionLabel(component: Component): string {
  return props.formatComponentOptionLabelFn
    ? props.formatComponentOptionLabelFn(component)
    : `${component.name} (#${component.id}) · ${component.status}`
}

function handleInspectorFocusIn(event: FocusEvent): void {
  const target = event.target
  if (!(target instanceof Element)) {
    return
  }
  let key = inputElementKeys.get(target)
  if (!key) {
    key = `inspector:${internalSelectedPath.value ?? 'none'}:${++inputElementSequence}`
    inputElementKeys.set(target, key)
  }
  editor.beginInputSession(key)
}

function handleInspectorFocusOut(event: FocusEvent): void {
  const target = event.target
  if (!(target instanceof Element)) {
    editor.endInputSession()
    return
  }
  editor.endInputSession(inputElementKeys.get(target))
}

function getFirstInvalidPath(): EditableStepPath | null {
  return validationErrors.value[0]?.path ?? null
}

async function locateNode(path: EditableStepPath): Promise<void> {
  const target = projectedGraph.value.nodes.find(
    (node: StepGraphNode): boolean => node.path === path
  )
  if (!target) {
    return
  }

  const nodeStates = { ...displayState.value.nodeStates }
  let parentPath = target.parentPath
  let displayStateChanged = false
  while (parentPath) {
    const parentState = nodeStates[parentPath]
    if (parentState?.collapsed) {
      nodeStates[parentPath] = {
        ...parentState,
        collapsed: false
      }
      displayStateChanged = true
    }
    parentPath =
      projectedGraph.value.nodes.find(
        (node: StepGraphNode): boolean => node.path === parentPath
      )?.parentPath ?? null
  }
  if (displayStateChanged) {
    editor.commitDisplayState({
      ...displayState.value,
      nodeStates
    })
  }

  selectOnly(path)
  inspectorTab.value = 'config'
  if (viewportMode.value === 'compact') {
    mobileInspectorOpen.value = true
  } else {
    inspectorCollapsed.value = false
  }
  await nextTick()
  await focusNode(path)
  emit('locate', path)
}

function requestSave(): void {
  editor.endInputSession()
  const invalidPath = getFirstInvalidPath()
  if (invalidPath) {
    const message = '请先修正步骤配置错误。'
    void locateNode(invalidPath)
    emit('error', {
      message,
      path: invalidPath,
      source: 'validation'
    })
    ElMessage.error(message)
    return
  }
  emit(
    'save',
    JSON.parse(JSON.stringify(workingStepDrafts.value)) as StepDraft[]
  )
}

function handleUndo(): void {
  if (!editor.undo()) {
    emit('undo')
    return
  }
  emit('undo')
}

function handleRedo(): void {
  if (!editor.redo()) {
    emit('redo')
    return
  }
  emit('redo')
}

function navigateSelection(command: StepCanvasShortcutCommand): void {
  const current = selectedNode.value
  const nodes = canvasGraph.value.nodes.filter(
    (node: StepGraphNode): boolean => node.kind !== 'root'
  )
  if (nodes.length === 0) {
    return
  }
  if (!current) {
    selectOnly(nodes[0].path)
    void focusNode(nodes[0].path)
    return
  }

  const currentCenter = {
    x: current.position.x + current.width / 2,
    y: current.position.y + current.height / 2
  }
  const horizontal =
    command === 'navigate-left' || command === 'navigate-right'
  const positive =
    command === 'navigate-right' || command === 'navigate-down'
  const candidate = nodes
    .filter((node: StepGraphNode): boolean => node.path !== current.path)
    .map((node: StepGraphNode): { node: StepGraphNode; score: number } | null => {
      const center = {
        x: node.position.x + node.width / 2,
        y: node.position.y + node.height / 2
      }
      const primary = horizontal
        ? center.x - currentCenter.x
        : center.y - currentCenter.y
      if ((positive && primary <= 0) || (!positive && primary >= 0)) {
        return null
      }
      const secondary = horizontal
        ? Math.abs(center.y - currentCenter.y)
        : Math.abs(center.x - currentCenter.x)
      return {
        node,
        score: Math.abs(primary) + secondary * 0.35
      }
    })
    .filter(
      (
        item: { node: StepGraphNode; score: number } | null
      ): item is { node: StepGraphNode; score: number } => item !== null
    )
    .sort(
      (
        left: { node: StepGraphNode; score: number },
        right: { node: StepGraphNode; score: number }
      ): number => left.score - right.score
    )[0]?.node
  if (!candidate) {
    return
  }
  selectOnly(candidate.path)
  void focusNode(candidate.path)
}

function reorderSelectedByKeyboard(direction: -1 | 1): void {
  const paths = getSelectedEditablePaths()
  if (paths.length !== 1) {
    reportCommandError(
      new Error('键盘排序需要先选择一个可编辑步骤。'),
      '步骤排序失败。'
    )
    return
  }

  const sourcePath = paths[0]
  const parsed = parseStepStructurePath(sourcePath)
  const sourceIndex =
    parsed?.kind === 'top-step'
      ? parsed.topIndex
      : parsed?.kind === 'branch-child' || parsed?.kind === 'else-child'
        ? parsed.childIndex
        : null
  if (sourceIndex === null) {
    return
  }

  const containerPath = getStepContainerPath(sourcePath)
  const targetIndex = sourceIndex + direction
  const containerLength = getStepContainerLength(
    workingStepDrafts.value,
    containerPath
  )
  if (targetIndex < 0 || targetIndex >= containerLength) {
    commandStatusMessage.value =
      direction < 0 ? '当前步骤已在本层级最前。' : '当前步骤已在本层级最后。'
    return
  }

  try {
    const result = reorderStepDrafts(
      workingStepDrafts.value,
      containerPath,
      sourceIndex,
      targetIndex
    )
    commitStepMutation(result, {
      kind: 'reorder',
      sourcePath,
      targetContainerPath: containerPath,
      insertionIndex: targetIndex
    })
  } catch (error: unknown) {
    reportCommandError(error, '步骤排序失败。', sourcePath)
  }
}

function handleWindowKeydown(event: KeyboardEvent): void {
  if (!props.visible) {
    return
  }
  const command = resolveStepCanvasShortcut(event)
  if (!command) {
    return
  }
  event.preventDefault()
  if (command === 'save') requestSave()
  else if (command === 'undo') handleUndo()
  else if (command === 'redo') handleRedo()
  else if (command === 'copy') copySelected()
  else if (command === 'cut') void cutSelected()
  else if (command === 'paste') pasteSelected()
  else if (command === 'duplicate') duplicateSelected()
  else if (command === 'delete') void deleteSelected()
  else if (command === 'fit-view') void fitView()
  else if (command === 'reset-zoom') void resetZoom()
  else if (command === 'auto-layout') void autoLayout()
  else if (command === 'create-step') handleCreateStep('wait')
  else if (command === 'open-inspector' && internalSelectedPath.value) {
    openNodeInspector(internalSelectedPath.value)
  }
  else if (command === 'close') void handleCloseRequest()
  else if (command === 'reorder-previous') reorderSelectedByKeyboard(-1)
  else if (command === 'reorder-next') reorderSelectedByKeyboard(1)
  else navigateSelection(command)
}

function handleFlowInit(store: VueFlowStore): void {
  flowStore.value = store
  viewportReady.value = false
  viewport.value = store.getViewport()
}

function handlePaneReady(store: VueFlowStore): void {
  if (!props.visible) {
    return
  }
  flowStore.value = store
  viewport.value = store.getViewport()
  viewportReady.value = true
  void nextTick().then(async (): Promise<void> => {
    syncFlowSelection()
    await fitView()
    emit('ready')
  })
}

function closeImmediately(): void {
  emit('request-close')
  emit('update:visible', false)
}

async function handleCloseRequest(): Promise<void> {
  if (!businessDirty.value) {
    closeImmediately()
    return
  }
  try {
    await ElMessageBox.confirm(
      '步骤存在未保存的业务变更。请选择保存、放弃或继续编辑。',
      '未保存的步骤',
      {
        type: 'warning',
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
        distinguishCancelAndClose: true,
        closeOnClickModal: false
      }
    )
    requestSave()
  } catch (action: unknown) {
    if (action === 'cancel') {
      editor.initialize(props.stepDrafts)
      closeImmediately()
    }
  }
}

function handleVisibilityUpdate(value: boolean): void {
  if (value) {
    emit('update:visible', true)
  } else {
    void handleCloseRequest()
  }
}

function toggleLibrary(): void {
  if (viewportMode.value === 'compact') {
    mobileLibraryOpen.value = true
    return
  }
  leftCollapsed.value = !leftCollapsed.value
}

function toggleInspector(): void {
  if (viewportMode.value === 'compact') {
    mobileInspectorOpen.value = true
    return
  }
  inspectorCollapsed.value = !inspectorCollapsed.value
}

function expandLibrary(): void {
  leftCollapsed.value = false
}

function expandInspector(): void {
  inspectorCollapsed.value = false
}

function handleBackgroundPatch(patch: StepCanvasBackgroundPatch): void {
  patchBackground(patch)
}

async function handleBackgroundFile(file: File): Promise<void> {
  backgroundBusy.value = true
  try {
    await saveBackgroundImage(file)
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '背景图片处理失败。'
    ElMessage.error(message)
    emit('background-error', message)
  } finally {
    backgroundBusy.value = false
  }
}

async function handleBackgroundRemove(): Promise<void> {
  backgroundBusy.value = true
  try {
    await clearBackgroundImage()
  } catch {
    const message = '背景图片已从画布移除，但浏览器本地文件清理失败。'
    ElMessage.warning(message)
    emit('background-error', message)
  } finally {
    backgroundBusy.value = false
  }
}

watch(
  () => props.selectedPath,
  (path: StepStructurePath | null): void => {
    selectedPaths.value = new Set(path ? [path] : [])
    setSelectedPath(path)
    void nextTick().then(syncFlowSelection)
    if (path && props.visible) {
      void focusNode(path)
    }
  }
)

watch(
  referencedComponentIds,
  (componentIds: number[]): void => {
    if (props.visible && componentIds.length > 0) {
      emit('request-component-previews', componentIds)
    }
  },
  { immediate: true }
)

watch(
  workingStepDrafts,
  (): void => {
    if (suppressDraftGraphRebuild) {
      suppressDraftGraphRebuild = false
      return
    }
    rebuildGraphsFully()
  },
  { deep: true, flush: 'sync' }
)

watch(
  displayState,
  (): void => {
    if (suppressDisplayGraphRebuild) {
      suppressDisplayGraphRebuild = false
      return
    }
    rebuildGraphsFully()
  },
  { deep: true, flush: 'sync' }
)

watch(
  () => [
    props.title,
    props.componentPreviews,
    props.validateStepFn
  ] as const,
  (): void => {
    rebuildGraphsFully()
  },
  { deep: true }
)

watch(
  projectedGraph,
  (graph: StepGraph): void => {
    const availablePaths = new Set(
      graph.nodes.map((node: StepGraphNode): StepStructurePath => node.path)
    )
    if (
      internalSelectedPath.value &&
      !availablePaths.has(internalSelectedPath.value) &&
      selectedBranchDraftId.value !== null
    ) {
      workingStepDrafts.value.some((step: StepDraft, topIndex: number): boolean => {
        const branchIndex = step.conditionalBranches.findIndex(
          (item: ConditionalBranchDraft): boolean =>
            item.id === selectedBranchDraftId.value
        )
        if (branchIndex < 0) {
          return false
        }
        const migratedPath = graph.nodes.find(
          (node: StepGraphNode): boolean =>
            node.kind === 'branch-lane' &&
            node.parentPath === `top:${topIndex}` &&
            node.order === branchIndex
        )?.path
        if (!migratedPath) {
          return false
        }
        selectedPaths.value = new Set([migratedPath])
        setSelectedPath(migratedPath)
        return true
      })
    }
    const nextSelectedPaths = new Set(
      [...selectedPaths.value].filter((path: StepStructurePath): boolean =>
        availablePaths.has(path)
      )
    )
    if (nextSelectedPaths.size !== selectedPaths.value.size) {
      selectedPaths.value = nextSelectedPaths
    }
    if (
      internalSelectedPath.value &&
      !availablePaths.has(internalSelectedPath.value)
    ) {
      setSelectedPath(nextSelectedPaths.values().next().value ?? null)
    }
  }
)

watch(
  viewportMode,
  (
    mode: StepCanvasViewportMode,
    previousMode: StepCanvasViewportMode | undefined
  ): void => {
    mobileLibraryOpen.value = false
    mobileInspectorOpen.value = false
    if (mode === previousMode) {
      return
    }
    if (mode === 'desktop') {
      leftCollapsed.value = false
      inspectorCollapsed.value = false
    } else if (mode === 'medium') {
      leftCollapsed.value = true
      inspectorCollapsed.value = false
    }
  },
  { immediate: true }
)

watch(
  () => props.visible,
  (visible: boolean, previousVisible: boolean | undefined): void => {
    setStepCanvasBodyMode(bodyModeOwner, visible)
    if (visible) {
      if (previousVisible === false) {
        editor.initialize(props.stepDrafts)
      }
      if (viewportReady.value) {
        void nextTick().then((): Promise<void> => fitView())
      }
    } else {
      viewportReady.value = false
      flowStore.value = null
    }
  },
  { immediate: true }
)

watch(
  preferencesLoaded,
  (loaded: boolean): void => {
    if (loaded) {
      editor.initialize(props.stepDrafts)
    }
  }
)

watch(
  () => [props.userId, props.workspaceId, props.testCaseId] as const,
  (): void => {
    editor.initialize(props.stepDrafts)
    selectOnly(props.selectedPath)
  }
)

watch(
  displayState,
  (state: StepGraphDisplayState): void => {
    if (preferencesLoaded.value) {
      emit('display-state-change', state)
    }
  },
  { deep: true }
)

watch(
  preferenceError,
  (message: string): void => {
    if (message) {
      emit('background-error', message)
      emit('error', {
        message,
        path: null,
        source: 'preference'
      })
    }
  }
)

onMounted((): void => {
  window.addEventListener('keydown', handleWindowKeydown)
})

onBeforeUnmount((): void => {
  window.removeEventListener('keydown', handleWindowKeydown)
  setStepCanvasBodyMode(bodyModeOwner, false)
})

defineExpose({
  fitView,
  autoLayout,
  focusNode,
  markSaved: editor.markSaved,
  async locate(path: EditableStepPath): Promise<void> {
    await locateNode(path)
  }
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    append-to-body
    body-class="step-canvas-dialog-body"
    class="step-canvas-dialog"
    destroy-on-close
    fullscreen
    modal-class="step-canvas-overlay"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    @update:model-value="handleVisibilityUpdate"
    @closed="emit('closed')"
  >
    <div class="step-canvas-workbench">
      <StepCanvasToolbar
        :title="title"
        :subtitle="testCaseCode"
        :mode="viewportMode"
        :dirty="businessDirty"
        :saving="saving"
        :can-undo="commandCanUndo"
        :can-redo="commandCanRedo"
        :left-collapsed="leftCollapsed"
        :inspector-collapsed="inspectorCollapsed"
        :viewport-ready="viewportReady"
        @close="handleCloseRequest"
        @undo="handleUndo"
        @redo="handleRedo"
        @auto-layout="autoLayout"
        @fit-view="fitView"
        @save="requestSave"
        @toggle-library="toggleLibrary"
        @toggle-inspector="toggleInspector"
      >
        <template #background-control>
          <StepCanvasBackgroundControl
            :preference="displayState.background"
            :has-image="Boolean(backgroundImageUrl)"
            :busy="backgroundBusy"
            :compact="viewportMode !== 'desktop'"
            @patch="handleBackgroundPatch"
            @select-image="handleBackgroundFile"
            @remove-image="handleBackgroundRemove"
          />
        </template>
        <template v-if="slots.toolbarActions" #secondary-actions>
          <slot name="toolbar-actions" />
        </template>
      </StepCanvasToolbar>

      <main class="step-canvas-main" :style="workspaceGridStyle">
        <StepCanvasSidebar
          v-if="viewportMode !== 'compact'"
          :nodes="projectedGraph.nodes"
          :node-states="displayState.nodeStates"
          :selected-path="internalSelectedPath"
          :collapsed="leftCollapsed"
          :allow-component-call="allowComponentCall"
          @request-expand="expandLibrary"
          @create-step="handleCreateStep"
          @palette-drag-end="handlePaletteDragEnd"
          @palette-drag-start="handlePaletteDragStart"
          @select-node="handleSidebarSelect"
          @toggle-collapse="toggleNodeCollapse"
        />

        <section
          aria-label="用例步骤执行树画布"
          class="step-canvas-stage"
          :style="canvasStageStyle"
          @dragleave="handlePaletteDragLeave"
          @dragover="handlePaletteDragOver"
          @drop="handlePaletteDrop"
        >
          <div
            v-if="displayState.background.kind === 'image' && backgroundImageUrl"
            aria-hidden="true"
            class="step-canvas-image-background"
            :style="backgroundLayerStyle"
          />
          <VueFlow
            aria-label="可缩放的步骤执行树"
            class="step-canvas-flow"
            :nodes="flowNodes"
            :edges="flowEdges"
            :min-zoom="canvasMinZoom"
            :max-zoom="canvasMaxZoom"
            :nodes-connectable="false"
            :elements-selectable="true"
            :pan-on-drag="true"
            :pan-activation-key-code="'Space'"
            :zoom-on-scroll="true"
            :zoom-on-pinch="true"
            :zoom-on-double-click="false"
            :prevent-scrolling="true"
            :only-render-visible-elements="true"
            :default-marker-color="'#64748b'"
            @init="handleFlowInit"
            @pane-ready="handlePaneReady"
            @move="handleMove"
            @nodes-change="handleNodesChange"
            @node-click="handleNodeClick"
            @node-drag-start="handleNodeDragStart"
            @node-drag="handleNodeDrag"
            @node-drag-stop="handleNodeDragStop"
          >
            <template #node-root-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #node-step-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #node-conditional-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #node-branch-lane-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #node-component-call-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #node-component-preview-node="nodeProps">
              <StepCanvasNode v-bind="nodeProps" />
            </template>
            <template #edge-step-canvas-edge="edgeProps">
              <StepCanvasEdge v-bind="edgeProps" />
            </template>
            <Background
              v-if="displayState.background.kind === 'grid'"
              :gap="20"
              :size="1.25"
              bg-color="#f8fafc"
              color="#cbd5e1"
              variant="dots"
            />
            <MiniMap
              aria-label="步骤画布小地图"
              :height="viewportMode === 'compact' ? 82 : 112"
              mask-color="rgb(226 232 240 / 58%)"
              node-color="#bfdbfe"
              node-stroke-color="#2563eb"
              :node-border-radius="4"
              pannable
              position="bottom-left"
              :width="viewportMode === 'compact' ? 120 : 180"
              zoomable
              @node-click="handleNodeClick"
            />
            <Controls
              position="bottom-right"
              :show-fit-view="false"
              :show-interactive="false"
              :show-zoom="false"
            >
              <ControlButton
                :aria-label="viewportReady ? '放大画布' : '放大画布，画布正在初始化'"
                class="vue-flow__controls-zoomin"
                :disabled="!viewportReady || viewport.zoom >= canvasMaxZoom"
                :title="viewportReady ? '放大画布' : '画布视口正在初始化，请稍候'"
                @click="zoomIn"
              >
                <ZoomIn aria-hidden="true" />
              </ControlButton>
              <ControlButton
                :aria-label="viewportReady ? '缩小画布' : '缩小画布，画布正在初始化'"
                class="vue-flow__controls-zoomout"
                :disabled="!viewportReady || viewport.zoom <= canvasMinZoom"
                :title="viewportReady ? '缩小画布' : '画布视口正在初始化，请稍候'"
                @click="zoomOut"
              >
                <ZoomOut aria-hidden="true" />
              </ControlButton>
              <ControlButton
                :aria-label="viewportReady ? '适应画布视图' : '适应画布视图，画布正在初始化'"
                class="vue-flow__controls-fitview"
                :disabled="!viewportReady"
                :title="viewportReady ? '适应画布视图' : '画布视口正在初始化，请稍候'"
                @click="fitView"
              >
                <FullScreen aria-hidden="true" />
              </ControlButton>
            </Controls>
          </VueFlow>
          <StepCanvasLegend
            :connection-style="displayState.connectionStyle"
            :show-edge-labels="showEdgeLabels"
            @update:connection-style="handleConnectionStyleChange"
          />
          <div
            v-if="dropCandidate"
            aria-hidden="true"
            class="step-drop-indicator"
            :class="{ 'is-invalid': !dropCandidate.valid }"
            :style="{
              width: `${dropCandidate.width}px`,
              transform: `translate3d(${dropCandidate.x}px, ${dropCandidate.y}px, 0)`
            }"
          />
          <div
            v-if="dropCandidate"
            class="step-drop-feedback"
            :class="{ 'is-invalid': !dropCandidate.valid }"
            role="status"
          >
            {{
              dropCandidate.valid
                ? dropCandidate.mode === 'create'
                  ? '释放以新增到当前插入位'
                  : '释放以插入到当前层级'
                : dropCandidate.reason
            }}
          </div>
        </section>

        <StepCanvasInspectorPanel
          v-if="viewportMode !== 'compact'"
          v-model:active-tab="inspectorTab"
          :selected-node="selectedNode"
          :collapsed="inspectorCollapsed"
          @request-expand="expandInspector"
        >
          <template #default="slotProps">
            <slot
              v-if="slots.inspector"
              name="inspector"
              :node="slotProps.node"
              :active-tab="slotProps.activeTab"
            />
            <div
              v-else
              @focusin.capture="handleInspectorFocusIn"
              @focusout.capture="handleInspectorFocusOut"
            >
              <StepCanvasInspectorContent
                :active-tab="slotProps.activeTab"
                :selected-node="slotProps.node"
                :selected-step="selectedStep"
                :selected-branch="selectedBranch"
                :selected-else-step="selectedElseStep"
                :selected-paths="[...selectedPaths]"
                :editable-nodes="editableNodes"
                :display-node-state="selectedDisplayState"
                :annotations="displayState.annotations"
                :templates="templates"
                :components="components"
                :allow-component-call="allowComponentCall"
                :validate-step-fn="validateStepFn"
                :get-step-template-options-fn="getStepTemplateOptions"
                :get-step-template-hint-fn="getStepTemplateHint"
                :format-component-option-label-fn="formatComponentOptionLabel"
                @update-step-type="updateSelectedStepType"
                @update-child-step-type="updateChildStepType"
                @update-branch-key="updateSelectedBranchKey"
                @command="handleInspectorCommand"
                @apply-style="applySelectedStyle"
                @reset-style="resetSelectedStyle"
                @create-annotation="createAnnotation"
                @delete-annotation="deleteAnnotation"
              />
            </div>
          </template>
        </StepCanvasInspectorPanel>
      </main>

      <StepCanvasStatusBar
        :step-count="stepCount"
        :branch-count="branchCount"
        :component-count="componentCount"
        :selected-count="selectedPaths.size"
        :error-count="resolvedErrorCount"
        :errors="validationErrors"
        :zoom-percent="zoomPercent"
        :message="resolvedStatusMessage"
        :loading-preferences="!preferencesLoaded"
        @show-errors="emit('show-errors')"
        @locate-error="locateNode"
      />

      <el-drawer
        :model-value="mobileLibraryOpen"
        append-to-body
        class="step-canvas-mobile-drawer"
        direction="ltr"
        modal-class="step-canvas-drawer-overlay"
        :modal="true"
        size="82%"
        :with-header="false"
        @update:model-value="mobileLibraryOpen = $event"
      >
        <div class="mobile-drawer-shell">
          <div class="mobile-drawer-header">
            <strong>节点库与大纲</strong>
            <el-button
              :icon="Close"
              aria-label="关闭节点库"
              circle
              text
              @click="mobileLibraryOpen = false"
            />
          </div>
          <StepCanvasSidebar
            :nodes="projectedGraph.nodes"
            :node-states="displayState.nodeStates"
            :selected-path="internalSelectedPath"
            :allow-component-call="allowComponentCall"
            @create-step="handleCreateStep"
            @palette-drag-end="handlePaletteDragEnd"
            @palette-drag-start="handlePaletteDragStart"
            @select-node="handleSidebarSelect"
            @toggle-collapse="toggleNodeCollapse"
          />
        </div>
      </el-drawer>

      <el-drawer
        :model-value="mobileInspectorOpen"
        append-to-body
        class="step-canvas-mobile-drawer step-canvas-mobile-inspector"
        direction="btt"
        modal-class="step-canvas-drawer-overlay"
        :modal="true"
        size="70%"
        :with-header="false"
        @update:model-value="mobileInspectorOpen = $event"
      >
        <div class="mobile-drawer-shell">
          <div class="mobile-drawer-header">
            <strong>节点检查器</strong>
            <el-button
              :icon="Close"
              aria-label="关闭节点检查器"
              circle
              text
              @click="mobileInspectorOpen = false"
            />
          </div>
          <StepCanvasInspectorPanel
            v-model:active-tab="inspectorTab"
            :selected-node="selectedNode"
          >
            <template #default="slotProps">
              <slot
                v-if="slots.inspector"
                name="inspector"
                :node="slotProps.node"
                :active-tab="slotProps.activeTab"
              />
              <div
                v-else
                @focusin.capture="handleInspectorFocusIn"
                @focusout.capture="handleInspectorFocusOut"
              >
                <StepCanvasInspectorContent
                  :active-tab="slotProps.activeTab"
                  :selected-node="slotProps.node"
                  :selected-step="selectedStep"
                  :selected-branch="selectedBranch"
                  :selected-else-step="selectedElseStep"
                  :selected-paths="[...selectedPaths]"
                  :editable-nodes="editableNodes"
                  :display-node-state="selectedDisplayState"
                  :annotations="displayState.annotations"
                  :templates="templates"
                  :components="components"
                  :allow-component-call="allowComponentCall"
                  :validate-step-fn="validateStepFn"
                  :get-step-template-options-fn="getStepTemplateOptions"
                  :get-step-template-hint-fn="getStepTemplateHint"
                  :format-component-option-label-fn="formatComponentOptionLabel"
                  @update-step-type="updateSelectedStepType"
                  @update-child-step-type="updateChildStepType"
                  @update-branch-key="updateSelectedBranchKey"
                  @command="handleInspectorCommand"
                  @apply-style="applySelectedStyle"
                  @reset-style="resetSelectedStyle"
                  @create-annotation="createAnnotation"
                  @delete-annotation="deleteAnnotation"
                />
              </div>
            </template>
          </StepCanvasInspectorPanel>
        </div>
      </el-drawer>
    </div>
  </el-dialog>
</template>

<style scoped>
.step-canvas-workbench {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;
}

.step-canvas-main {
  display: grid;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  flex: 1 1 0;
  overflow: hidden;
}

.step-canvas-stage {
  position: relative;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.step-canvas-image-background {
  position: absolute;
  z-index: 0;
  inset: 0;
  pointer-events: none;
}

.step-canvas-flow {
  position: absolute;
  z-index: 1;
  inset: 0;
  min-width: 0;
  min-height: 0;
  background: transparent;
}

.step-canvas-flow :deep(.vue-flow__node:focus-visible) {
  outline: 2px solid #2563eb;
  outline-offset: 3px;
}

.step-drop-indicator {
  position: absolute;
  z-index: 7;
  top: 0;
  left: 0;
  height: 3px;
  border-radius: 2px;
  opacity: 0.9;
  background: #2563eb;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 14%);
  pointer-events: none;
  transform-origin: top left;
  transition: opacity 120ms ease;
}

.step-drop-indicator::before,
.step-drop-indicator::after {
  position: absolute;
  top: -4px;
  width: 3px;
  height: 11px;
  border-radius: 2px;
  background: inherit;
  content: '';
}

.step-drop-indicator::before {
  left: 0;
}

.step-drop-indicator::after {
  right: 0;
}

.step-drop-indicator.is-invalid {
  background: #e11d48;
  box-shadow: 0 0 0 3px rgb(225 29 72 / 14%);
}

.step-drop-feedback {
  position: absolute;
  z-index: 8;
  bottom: 40px;
  left: 50%;
  max-width: min(480px, calc(100% - 32px));
  padding: 6px 10px;
  overflow: hidden;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  color: #1e40af;
  opacity: 0.96;
  background: #eff6ff;
  box-shadow: 0 2px 8px rgb(15 23 42 / 10%);
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
  transform: translateX(-50%);
  transition: opacity 120ms ease;
}

.step-drop-feedback.is-invalid {
  border-color: #fda4af;
  color: #9f1239;
  background: #fff1f2;
}

.step-canvas-flow :deep(.vue-flow__controls),
.step-canvas-flow :deep(.vue-flow__minimap) {
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgb(15 23 42 / 10%);
}

.step-canvas-flow :deep(.vue-flow__controls-button) {
  border-radius: 0;
}

.mobile-drawer-shell {
  display: flex;
  min-width: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
}

.mobile-drawer-header {
  display: flex;
  height: 48px;
  flex: 0 0 48px;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e2e8f0;
}

@media (prefers-reduced-motion: reduce) {
  .step-canvas-flow :deep(.vue-flow__node),
  .step-canvas-flow :deep(.vue-flow__edge-path) {
    transition: none;
    animation: none;
  }
}

:global(.step-canvas-dialog.el-dialog) {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  min-width: 0;
  max-width: none;
  height: 100%;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border-radius: 0;
}

:global(.step-canvas-overlay.el-overlay) {
  width: 100vw;
  min-width: 0;
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

:global(.step-canvas-overlay .el-overlay-dialog) {
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

:global(.step-canvas-dialog .el-dialog__header) {
  display: none;
}

:global(.step-canvas-dialog .step-canvas-dialog-body) {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  min-width: 0;
  height: auto;
  min-height: 0;
  flex: 1 1 auto;
  padding: 0;
  overflow: hidden;
}

:global(body.step-canvas-open) {
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

:global(.step-canvas-drawer-overlay.el-overlay) {
  position: fixed;
  inset: 0;
  width: 100vw;
  min-width: 0;
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

:global(.step-canvas-drawer-overlay .el-drawer) {
  position: absolute;
}

:global(.step-canvas-mobile-drawer) {
  max-width: 360px;
  border-radius: 0;
}

:global(.step-canvas-mobile-inspector) {
  width: 100% !important;
  max-width: none;
  border-radius: 0;
}

:global(.step-canvas-mobile-drawer .el-drawer__body) {
  padding: 0;
  overflow: hidden;
}

:global(.step-canvas-mobile-drawer .step-canvas-sidebar),
:global(.step-canvas-mobile-drawer .step-canvas-inspector) {
  flex: 1;
  border: 0;
}
</style>
