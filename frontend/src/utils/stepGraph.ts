import { graphlib, layout as runDagreLayout } from '@dagrejs/dagre'

import type { StepWritePayload } from '@/types/models'
import type {
  BranchChildPath,
  ComponentPreviewPath,
  ConditionalBranchPath,
  EditableStepPath,
  ElseBranchPath,
  ElseChildPath,
  ParsedStepStructurePath,
  StepContainerPath,
  StepGraph,
  StepGraphAnnotation,
  StepGraphComponentStep,
  StepGraphDisplayState,
  StepGraphDropAssessment,
  StepGraphEdge,
  StepGraphEdgeVisual,
  StepGraphInsertionAssessment,
  StepGraphLayoutOptions,
  StepGraphMutationResult,
  StepGraphNode,
  StepGraphNodeDisplayState,
  StepGraphOperationErrorCode,
  StepGraphProjectionOptions,
  StepPathMigration,
  StepStructurePath,
  TopStepPath
} from '@/types/stepGraph'
import {
  buildStepWritePayload,
  formatStepSummary,
  getStepTypeLabel,
  validateStepDraft,
  type ConditionalBranchDraft,
  type StepDraft
} from '@/utils/steps'

const DEFAULT_NODE_WIDTH = 224
const DEFAULT_NODE_HEIGHT = 96
const COMPACT_NODE_WIDTH = 184
const COMPACT_NODE_HEIGHT = 72
const LARGE_NODE_WIDTH = 280
const LARGE_NODE_HEIGHT = 120
export const STEP_GRAPH_EDGE_LABEL_ZOOM_THRESHOLD = 0.6

interface CloneOrigins {
  stepPaths: WeakMap<StepDraft, EditableStepPath>
  branchPaths: WeakMap<ConditionalBranchDraft, ConditionalBranchPath>
  elsePaths: WeakMap<StepDraft, ElseBranchPath>
}

interface ClonedDraftTree {
  drafts: StepDraft[]
  origins: CloneOrigins
}

export class StepGraphOperationError extends Error {
  readonly code: StepGraphOperationErrorCode

  constructor(code: StepGraphOperationErrorCode, message: string) {
    super(message)
    this.name = 'StepGraphOperationError'
    this.code = code
  }
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value)
}

function decodePathSegment(value: string): string | null {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

function parseIndex(value: string): number | null {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null
}

export function createTopStepPath(index: number): TopStepPath {
  assertNonNegativeIndex(index)
  return `top:${index}`
}

export function createConditionalBranchPath(
  topIndex: number,
  branchKey: string
): ConditionalBranchPath {
  assertNonNegativeIndex(topIndex)
  if (!branchKey.trim()) {
    throw new StepGraphOperationError('INVALID_PATH', '条件分支路径需要非空 branchKey。')
  }
  return `${createTopStepPath(topIndex)}:branch:${encodePathSegment(branchKey)}`
}

export function createElseBranchPath(topIndex: number): ElseBranchPath {
  return `${createTopStepPath(topIndex)}:else`
}

export function createBranchChildPath(
  topIndex: number,
  branchKey: string,
  childIndex: number
): BranchChildPath {
  assertNonNegativeIndex(childIndex)
  return `${createConditionalBranchPath(topIndex, branchKey)}:child:${childIndex}`
}

export function createElseChildPath(topIndex: number, childIndex: number): ElseChildPath {
  assertNonNegativeIndex(childIndex)
  return `${createElseBranchPath(topIndex)}:child:${childIndex}`
}

export function createComponentPreviewPath(
  topIndex: number,
  childIndex: number
): ComponentPreviewPath {
  assertNonNegativeIndex(childIndex)
  return `${createTopStepPath(topIndex)}:component:child:${childIndex}`
}

export function parseStepStructurePath(path: string): ParsedStepStructurePath | null {
  if (path === 'root') {
    return { kind: 'root' }
  }

  let match = /^top:(\d+):component:child:(\d+)$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    const childIndex = parseIndex(match[2])
    return topIndex === null || childIndex === null
      ? null
      : { kind: 'component-preview', topIndex, childIndex }
  }

  match = /^top:(\d+):else:child:(\d+)$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    const childIndex = parseIndex(match[2])
    return topIndex === null || childIndex === null
      ? null
      : { kind: 'else-child', topIndex, childIndex }
  }

  match = /^top:(\d+):branch:(.+):child:(\d+)$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    const branchKey = decodePathSegment(match[2])
    const childIndex = parseIndex(match[3])
    return topIndex === null || branchKey === null || childIndex === null
      ? null
      : { kind: 'branch-child', topIndex, branchKey, childIndex }
  }

  match = /^top:(\d+):branch:(.+)$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    const branchKey = decodePathSegment(match[2])
    return topIndex === null || branchKey === null
      ? null
      : { kind: 'branch', topIndex, branchKey }
  }

  match = /^top:(\d+):else$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    return topIndex === null ? null : { kind: 'else', topIndex }
  }

  match = /^top:(\d+)$/.exec(path)
  if (match) {
    const topIndex = parseIndex(match[1])
    return topIndex === null ? null : { kind: 'top-step', topIndex }
  }

  return null
}

export function isEditableStepPath(path: string): path is EditableStepPath {
  const parsed = parseStepStructurePath(path)
  return (
    parsed?.kind === 'top-step' ||
    parsed?.kind === 'branch-child' ||
    parsed?.kind === 'else-child'
  )
}

export function getStepContainerPath(path: EditableStepPath): StepContainerPath {
  const parsed = parseStepStructurePath(path)
  if (parsed?.kind === 'top-step') {
    return 'root'
  }
  if (parsed?.kind === 'branch-child') {
    return createConditionalBranchPath(parsed.topIndex, parsed.branchKey)
  }
  if (parsed?.kind === 'else-child') {
    return createElseBranchPath(parsed.topIndex)
  }
  if (parsed?.kind === 'component-preview') {
    throw new StepGraphOperationError('READ_ONLY_PATH', '组件预览步骤为只读节点。')
  }
  throw invalidPath(path)
}

export function projectStepDraftsToGraph(
  drafts: readonly StepDraft[],
  options: StepGraphProjectionOptions = {}
): StepGraph {
  const nodes: StepGraphNode[] = [
    createGraphNode({
      path: 'root',
      kind: 'root',
      parentPath: null,
      order: 0,
      label: options.rootLabel?.trim() || '用例根节点',
      detail: `${drafts.length} 个顶层步骤`,
      typeLabel: '用例',
      summary: `${drafts.length} 个顶层步骤`
    })
  ]
  const edges: StepGraphEdge[] = []

  drafts.forEach((step: StepDraft, topIndex: number): void => {
    const topPath = createTopStepPath(topIndex)
    const componentPreview =
      step.componentId === null ? undefined : options.componentPreviews?.[step.componentId]
    const topDetail =
      step.type === 'conditional_branch'
        ? `${step.conditionalBranches.length} 个条件分支${step.elseBranchEnabled ? ' + 默认分支' : ''}`
        : step.type === 'component_call'
          ? componentPreview?.name || `组件 #${step.componentId ?? '--'}`
          : getStepTypeLabel(step.type)
    const presentation = buildStepPresentation(step, topIndex)
    const componentSummary =
      step.type === 'component_call' && componentPreview
        ? formatComponentPreviewSummary(componentPreview)
        : presentation.summary

    nodes.push(
      createGraphNode({
        path: topPath,
        kind: 'top-step',
        parentPath: 'root',
        order: topIndex,
        label: step.name.trim() || `${getStepTypeLabel(step.type)} ${topIndex + 1}`,
        detail: topDetail,
        typeLabel: getStepTypeLabel(step.type),
        summary: componentSummary,
        stepType: step.type,
        stepNo: topIndex + 1,
        timeoutMs: step.timeoutMs,
        retryTimes: step.retryTimes,
        errorCount: presentation.errorCount,
        editable: true,
        componentId: step.componentId,
        componentStatus: componentPreview?.status ?? null
      })
    )

    const previousTopPath = topIndex === 0 ? 'root' : createTopStepPath(topIndex - 1)
    edges.push(
      createGraphEdge(
        previousTopPath,
        topPath,
        'sequence',
        topIndex === 0 ? '开始' : '顺序执行',
        true
      )
    )

    if (step.type === 'conditional_branch') {
      projectConditionalBranches(step, topIndex, nodes, edges)
    }

    if (
      step.type === 'component_call' &&
      componentPreview &&
      componentPreview.loadState !== 'loading' &&
      componentPreview.loadState !== 'error'
    ) {
      projectComponentPreview(componentPreview, topIndex, topPath, nodes, edges)
    }
  })

  const editablePaths = new Set(
    nodes
      .filter((node: StepGraphNode): boolean => node.editable)
      .map((node: StepGraphNode): StepStructurePath => node.path)
  )
  for (const annotation of options.annotations ?? []) {
    if (!editablePaths.has(annotation.source) || !editablePaths.has(annotation.target)) {
      continue
    }
    edges.push(createAnnotationEdge(annotation))
  }

  return { nodes, edges }
}

function formatComponentPreviewSummary(
  componentPreview: NonNullable<StepGraphProjectionOptions['componentPreviews']>[number]
): string {
  if (componentPreview.loadState === 'loading') {
    return `${componentPreview.name} · 正在加载只读步骤`
  }
  if (componentPreview.loadState === 'error') {
    return `${componentPreview.name} · 加载失败：${componentPreview.errorMessage ?? '请稍后重试'}`
  }
  if (componentPreview.status !== 'published') {
    return `${componentPreview.name} · ${componentPreview.status} · 未发布，仅供预览`
  }
  return `${componentPreview.name} · published`
}

function projectConditionalBranches(
  step: StepDraft,
  topIndex: number,
  nodes: StepGraphNode[],
  edges: StepGraphEdge[]
): void {
  const topPath = createTopStepPath(topIndex)
  const usedBranchPathKeys = new Set<string>()

  step.conditionalBranches.forEach(
    (branch: ConditionalBranchDraft, branchIndex: number): void => {
      const branchPathKey = resolveProjectionBranchPathKey(
        branch,
        branchIndex,
        usedBranchPathKeys
      )
      const branchPath = createConditionalBranchPath(topIndex, branchPathKey)
      nodes.push(
        createGraphNode({
          path: branchPath,
          kind: 'branch-lane',
          parentPath: topPath,
          order: branchIndex,
          label: branch.branchName.trim() || branch.branchKey,
          detail: branch.conditionType,
          typeLabel: `条件 ${branchIndex + 1}`,
          summary: formatBranchConditionSummary(branch),
          branchKey: branch.branchKey
        })
      )
      edges.push(
        createGraphEdge(
          topPath,
          branchPath,
          'condition',
          branch.branchName.trim() || branch.branchKey,
          true
        )
      )
      projectBranchSteps(branch.steps, topIndex, branchPathKey, branchPath, nodes, edges)
    }
  )

  if (!step.elseBranchEnabled) {
    return
  }

  const elsePath = createElseBranchPath(topIndex)
  nodes.push(
    createGraphNode({
      path: elsePath,
      kind: 'else-lane',
      parentPath: topPath,
      order: step.conditionalBranches.length,
      label: step.elseBranchName.trim() || '默认分支',
      detail: '未命中任何条件时执行',
      typeLabel: 'Else 泳道',
      summary: '未命中任何条件时执行',
      branchKey: 'else'
    })
  )
  edges.push(createGraphEdge(topPath, elsePath, 'else', 'else', true))

  step.elseSteps.forEach((childStep: StepDraft, childIndex: number): void => {
    const childPath = createElseChildPath(topIndex, childIndex)
    nodes.push(
      createStepNode(childStep, childPath, elsePath, childIndex, 'branch-step', true)
    )
    const source = childIndex === 0 ? elsePath : createElseChildPath(topIndex, childIndex - 1)
    edges.push(createGraphEdge(source, childPath, 'sequence', '顺序执行', true))
  })
}

function resolveProjectionBranchPathKey(
  branch: ConditionalBranchDraft,
  branchIndex: number,
  usedKeys: Set<string>
): string {
  const branchKey = branch.branchKey.trim()
  if (branchKey && !usedKeys.has(branchKey)) {
    usedKeys.add(branchKey)
    return branchKey
  }
  const fallbackKey = `__draft_${Math.abs(branch.id)}_${branchIndex}`
  usedKeys.add(fallbackKey)
  return fallbackKey
}

function projectBranchSteps(
  steps: readonly StepDraft[],
  topIndex: number,
  branchKey: string,
  branchPath: ConditionalBranchPath,
  nodes: StepGraphNode[],
  edges: StepGraphEdge[]
): void {
  steps.forEach((childStep: StepDraft, childIndex: number): void => {
    const childPath = createBranchChildPath(topIndex, branchKey, childIndex)
    nodes.push(
      createStepNode(childStep, childPath, branchPath, childIndex, 'branch-step', true)
    )
    const source =
      childIndex === 0
        ? branchPath
        : createBranchChildPath(topIndex, branchKey, childIndex - 1)
    edges.push(createGraphEdge(source, childPath, 'sequence', '顺序执行', true))
  })
}

function projectComponentPreview(
  componentPreview: NonNullable<StepGraphProjectionOptions['componentPreviews']>[number],
  topIndex: number,
  topPath: TopStepPath,
  nodes: StepGraphNode[],
  edges: StepGraphEdge[]
): void {
  componentPreview.steps.forEach(
    (componentStep: StepGraphComponentStep, childIndex: number): void => {
      const childPath = createComponentPreviewPath(topIndex, childIndex)
      nodes.push(
        createGraphNode({
          path: childPath,
          kind: 'component-preview',
          parentPath: topPath,
          order: childIndex,
          label:
            componentStep.name.trim() ||
            `${getStepTypeLabel(componentStep.type)} ${childIndex + 1}`,
          detail: componentPreview.name,
          typeLabel: getStepTypeLabel(componentStep.type),
          summary: componentStep.summary?.trim() || `来自组件 ${componentPreview.name}`,
          stepType: componentStep.type,
          stepNo: childIndex + 1,
          timeoutMs: componentStep.timeoutMs ?? null,
          retryTimes: componentStep.retryTimes ?? null,
          errorCount: componentStep.errorCount ?? 0,
          readOnly: true,
          componentId: componentPreview.componentId,
          componentStatus: componentPreview.status
        })
      )
      const source =
        childIndex === 0 ? topPath : createComponentPreviewPath(topIndex, childIndex - 1)
      edges.push(createGraphEdge(source, childPath, 'component', '组件引用', true))
    }
  )
}

function createStepNode(
  step: StepDraft,
  path: EditableStepPath,
  parentPath: StepStructurePath,
  order: number,
  kind: 'branch-step',
  editable: boolean
): StepGraphNode {
  const presentation = buildStepPresentation(step, order)
  return createGraphNode({
    path,
    kind,
    parentPath,
    order,
    label: step.name.trim() || `${getStepTypeLabel(step.type)} ${order + 1}`,
    detail: getStepTypeLabel(step.type),
    typeLabel: getStepTypeLabel(step.type),
    summary: presentation.summary,
    stepType: step.type,
    stepNo: order + 1,
    timeoutMs: step.timeoutMs,
    retryTimes: step.retryTimes,
    errorCount: presentation.errorCount,
    editable
  })
}

function createGraphNode(
  input: Pick<
    StepGraphNode,
    | 'path'
    | 'kind'
    | 'parentPath'
    | 'order'
    | 'label'
    | 'detail'
    | 'typeLabel'
    | 'summary'
  > &
    Partial<
      Pick<
        StepGraphNode,
        | 'stepType'
        | 'stepNo'
        | 'timeoutMs'
        | 'retryTimes'
        | 'errorCount'
        | 'editable'
        | 'readOnly'
        | 'branchKey'
        | 'componentId'
        | 'componentStatus'
      >
    >
): StepGraphNode {
  const compact = input.kind === 'branch-lane' || input.kind === 'else-lane'
  return {
    id: input.path,
    path: input.path,
    kind: input.kind,
    parentPath: input.parentPath,
    order: input.order,
    label: input.label,
    detail: input.detail,
    typeLabel: input.typeLabel,
    summary: input.summary,
    stepType: input.stepType ?? null,
    stepNo: input.stepNo ?? null,
    timeoutMs: input.timeoutMs ?? null,
    retryTimes: input.retryTimes ?? null,
    errorCount: input.errorCount ?? 0,
    editable: input.editable ?? false,
    readOnly: input.readOnly ?? false,
    branchKey: input.branchKey ?? null,
    componentId: input.componentId ?? null,
    componentStatus: input.componentStatus ?? null,
    hiddenDescendantCount: 0,
    position: { x: 0, y: 0 },
    width: compact ? COMPACT_NODE_WIDTH : DEFAULT_NODE_WIDTH,
    height: compact ? COMPACT_NODE_HEIGHT : DEFAULT_NODE_HEIGHT
  }
}

function buildStepPresentation(
  step: StepDraft,
  index: number
): { summary: string; errorCount: number } {
  const payload = buildStepWritePayload(step, index)
  const summary = formatStepSummary({
    type: step.type,
    payloadJson: payload.payloadJson,
    templateId: payload.templateId,
    componentId: payload.componentId,
    timeoutMs: payload.timeoutMs,
    retryTimes: payload.retryTimes
  })
  return {
    summary: summary.target,
    errorCount: Object.keys(validateStepDraft(step)).length
  }
}

function formatBranchConditionSummary(branch: ConditionalBranchDraft): string {
  if (branch.conditionType === 'selector_exists') {
    return `选择器 ${branch.selector.trim() || '--'}`
  }
  if (branch.conditionType === 'template_visible') {
    return `模板 #${branch.templateId ?? '--'}`
  }
  return `OCR ${branch.ocrTarget.text.trim() || '--'}`
}

function createGraphEdge(
  source: StepStructurePath,
  target: StepStructurePath,
  kind: StepGraphEdge['kind'],
  label: string,
  executable: boolean
): StepGraphEdge {
  return {
    id: `${kind}:${source}->${target}`,
    source,
    target,
    kind,
    label,
    executable,
    annotationOnly: !executable
  }
}

function createAnnotationEdge(annotation: StepGraphAnnotation): StepGraphEdge {
  const kind =
    annotation.kind === 'dependency' ? 'dependency-annotation' : 'parallel-annotation'
  const relationLabel = annotation.kind === 'dependency' ? '依赖' : '并行'
  return {
    id: `annotation:${annotation.id}`,
    source: annotation.source,
    target: annotation.target,
    kind,
    label: `${annotation.label?.trim() || relationLabel} · 仅标注`,
    executable: false,
    annotationOnly: true
  }
}

export function getStepGraphEdgeVisual(
  kind: StepGraphEdge['kind']
): StepGraphEdgeVisual {
  switch (kind) {
    case 'condition':
      return {
        color: '#d97706',
        dasharray: null,
        arrow: 'closed',
        doubleTrack: false
      }
    case 'else':
      return {
        color: '#64748b',
        dasharray: '7 5',
        arrow: 'closed',
        doubleTrack: false
      }
    case 'component':
      return {
        color: '#4f46e5',
        dasharray: '2 5',
        arrow: 'closed',
        doubleTrack: false
      }
    case 'dependency-annotation':
      return {
        color: '#64748b',
        dasharray: '7 5',
        arrow: 'open',
        doubleTrack: false
      }
    case 'parallel-annotation':
      return {
        color: '#0891b2',
        dasharray: '7 5',
        arrow: 'none',
        doubleTrack: true
      }
    case 'sequence':
    default:
      return {
        color: '#475569',
        dasharray: null,
        arrow: 'closed',
        doubleTrack: false
      }
  }
}

export function shouldShowStepGraphEdgeLabels(zoom: number): boolean {
  return Number.isFinite(zoom) && zoom >= STEP_GRAPH_EDGE_LABEL_ZOOM_THRESHOLD
}

export function applyStepGraphDisplayState(
  graph: StepGraph,
  displayState: Pick<StepGraphDisplayState, 'nodeStates'>
): StepGraph {
  return {
    nodes: graph.nodes.map((node: StepGraphNode): StepGraphNode => {
      const state = displayState.nodeStates[node.path]
      const dimensions = getDisplayDimensions(node, state)
      return {
        ...node,
        position: state?.position ? { ...state.position } : { ...node.position },
        ...dimensions
      }
    }),
    edges: graph.edges.map((edge: StepGraphEdge): StepGraphEdge => ({ ...edge }))
  }
}

function getDisplayDimensions(
  node: StepGraphNode,
  state: StepGraphNodeDisplayState | undefined
): Pick<StepGraphNode, 'width' | 'height'> {
  if (node.kind === 'branch-lane' || node.kind === 'else-lane') {
    return { width: COMPACT_NODE_WIDTH, height: COMPACT_NODE_HEIGHT }
  }
  if (state?.size === 'small') {
    return { width: COMPACT_NODE_WIDTH, height: COMPACT_NODE_HEIGHT }
  }
  if (state?.size === 'large') {
    return { width: LARGE_NODE_WIDTH, height: LARGE_NODE_HEIGHT }
  }
  return { width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT }
}

export function filterCollapsedStepGraph(
  graph: StepGraph,
  displayState: Pick<StepGraphDisplayState, 'nodeStates'>
): StepGraph {
  const nodeByPath = new Map(
    graph.nodes.map((node: StepGraphNode): [StepStructurePath, StepGraphNode] => [node.path, node])
  )
  const collapsedPaths = new Set(
    Object.entries(displayState.nodeStates)
      .filter(([, state]: [string, StepGraphNodeDisplayState]): boolean => state.collapsed === true)
      .map(([path]: [string, StepGraphNodeDisplayState]): string => path)
  )
  const hiddenPaths = new Set<StepStructurePath>()

  for (const node of graph.nodes) {
    let parentPath = node.parentPath
    while (parentPath) {
      if (collapsedPaths.has(parentPath)) {
        hiddenPaths.add(node.path)
        break
      }
      parentPath = nodeByPath.get(parentPath)?.parentPath ?? null
    }
  }

  const visibleNodes = graph.nodes
    .filter((node: StepGraphNode): boolean => !hiddenPaths.has(node.path))
    .map((node: StepGraphNode): StepGraphNode => ({
      ...node,
      position: { ...node.position },
      hiddenDescendantCount: collapsedPaths.has(node.path)
        ? countDescendants(node.path, graph.nodes, nodeByPath)
        : 0
    }))
  const visiblePaths = new Set(
    visibleNodes.map((node: StepGraphNode): StepStructurePath => node.path)
  )

  return {
    nodes: visibleNodes,
    edges: graph.edges
      .filter(
        (edge: StepGraphEdge): boolean =>
          visiblePaths.has(edge.source) && visiblePaths.has(edge.target)
      )
      .map((edge: StepGraphEdge): StepGraphEdge => ({ ...edge }))
  }
}

function countDescendants(
  ancestorPath: StepStructurePath,
  nodes: readonly StepGraphNode[],
  nodeByPath: ReadonlyMap<StepStructurePath, StepGraphNode>
): number {
  return nodes.filter((node: StepGraphNode): boolean => {
    let parentPath = node.parentPath
    while (parentPath) {
      if (parentPath === ancestorPath) {
        return true
      }
      parentPath = nodeByPath.get(parentPath)?.parentPath ?? null
    }
    return false
  }).length
}

export function layoutStepGraph(
  graph: StepGraph,
  options: StepGraphLayoutOptions = {}
): StepGraph {
  const dagreGraph = new graphlib.Graph({ multigraph: true })
  dagreGraph.setGraph({
    rankdir: 'TB',
    ranker: 'tight-tree',
    rankalign: 'center',
    ranksep: options.rankSeparation ?? 96,
    nodesep: options.nodeSeparation ?? 48,
    edgesep: options.edgeSeparation ?? 24,
    marginx: options.marginX ?? 24,
    marginy: options.marginY ?? 24
  })
  dagreGraph.setDefaultEdgeLabel((): Record<string, never> => ({}))

  graph.nodes.forEach((node: StepGraphNode): void => {
    dagreGraph.setNode(node.path, {
      width: node.width,
      height: node.height
    })
  })
  graph.edges
    .filter((edge: StepGraphEdge): boolean => !edge.annotationOnly)
    .forEach((edge: StepGraphEdge): void => {
      dagreGraph.setEdge(
        edge.source,
        edge.target,
        {
          weight: edge.kind === 'sequence' ? 2 : 1,
          minlen: 1
        },
        edge.id
      )
    })

  runDagreLayout(dagreGraph)

  return {
    nodes: graph.nodes.map((node: StepGraphNode): StepGraphNode => {
      const laidOutNode = dagreGraph.node(node.path) as
        | { x: number; y: number; width: number; height: number }
        | undefined
      if (!laidOutNode) {
        return { ...node, position: { ...node.position } }
      }
      return {
        ...node,
        position: {
          x: laidOutNode.x - laidOutNode.width / 2,
          y: laidOutNode.y - laidOutNode.height / 2
        }
      }
    }),
    edges: graph.edges.map((edge: StepGraphEdge): StepGraphEdge => ({ ...edge }))
  }
}

export function normalizeStepDraftTree(drafts: readonly StepDraft[]): StepDraft[] {
  assertValidDraftStructure(drafts)
  const clonedDrafts = deepClone(drafts) as StepDraft[]
  normalizeStepNumbers(clonedDrafts)
  return clonedDrafts
}

export function cloneStepDraft(step: StepDraft): StepDraft {
  return deepClone(step)
}

export function insertStepDraft(
  drafts: readonly StepDraft[],
  containerPath: StepContainerPath,
  index: number,
  step: StepDraft
): StepGraphMutationResult<StepDraft> {
  assertValidDraftStructure(drafts)
  assertValidDraftStructure([step])
  const tree = cloneDraftTreeWithOrigins(drafts)
  const target = getMutableContainer(tree.drafts, containerPath)
  assertInsertionIndex(index, target.length)
  assertContainerAcceptsStep(containerPath, step)

  target.splice(index, 0, cloneStepDraft(step))
  normalizeStepNumbers(tree.drafts)
  const pathMigration = collectPathMigration(tree.drafts, tree.origins)
  return {
    drafts: tree.drafts,
    pathMigration,
    focusPath: createChildPath(containerPath, index)
  }
}

export function reorderStepDrafts(
  drafts: readonly StepDraft[],
  containerPath: StepContainerPath,
  fromIndex: number,
  toIndex: number
): StepGraphMutationResult<StepDraft> {
  assertValidDraftStructure(drafts)
  const tree = cloneDraftTreeWithOrigins(drafts)
  const container = getMutableContainer(tree.drafts, containerPath)
  assertExistingIndex(fromIndex, container.length)
  assertExistingIndex(toIndex, container.length)

  const [movedStep] = container.splice(fromIndex, 1)
  container.splice(toIndex, 0, movedStep)
  normalizeStepNumbers(tree.drafts)
  const pathMigration = collectPathMigration(tree.drafts, tree.origins)
  const oldPath = createChildPath(containerPath, fromIndex)
  return {
    drafts: tree.drafts,
    pathMigration,
    focusPath: pathMigration[oldPath] as EditableStepPath
  }
}

export function moveStepDraft(
  drafts: readonly StepDraft[],
  sourcePath: EditableStepPath,
  targetContainerPath: StepContainerPath,
  targetIndex: number
): StepGraphMutationResult<StepDraft> {
  assertValidDraftStructure(drafts)
  const sourceContainerPath = getStepContainerPath(sourcePath)
  if (sourceContainerPath === targetContainerPath) {
    const source = parseEditablePath(sourcePath)
    return reorderStepDrafts(drafts, sourceContainerPath, source.childIndex, targetIndex)
  }

  const sourceStep = getStepAtPath(drafts, sourcePath)
  assertContainerAcceptsStep(targetContainerPath, sourceStep)
  const sourceContainer = getReadonlyContainer(drafts, sourceContainerPath)
  if (sourceContainerPath !== 'root' && sourceContainer.length === 1) {
    throw new StepGraphOperationError('EMPTY_BRANCH', '移动会清空条件分支，操作已拒绝。')
  }

  const targetBeforeMove = getReadonlyContainer(drafts, targetContainerPath)
  assertInsertionIndex(targetIndex, targetBeforeMove.length)

  const tree = cloneDraftTreeWithOrigins(drafts)
  const mutableSourceContainer = getMutableContainer(tree.drafts, sourceContainerPath)
  const source = parseEditablePath(sourcePath)
  const [movedStep] = mutableSourceContainer.splice(source.childIndex, 1)
  const adjustedTargetPath = adjustContainerAfterTopRemoval(
    targetContainerPath,
    sourceContainerPath,
    source.childIndex
  )
  const mutableTargetContainer = getMutableContainer(tree.drafts, adjustedTargetPath)
  assertInsertionIndex(targetIndex, mutableTargetContainer.length)
  mutableTargetContainer.splice(targetIndex, 0, movedStep)

  normalizeStepNumbers(tree.drafts)
  const pathMigration = collectPathMigration(tree.drafts, tree.origins)
  return {
    drafts: tree.drafts,
    pathMigration,
    focusPath: pathMigration[sourcePath] as EditableStepPath
  }
}

export function assessStepDraftDrop(
  drafts: readonly StepDraft[],
  sourcePath: StepStructurePath,
  targetContainerPath: StepContainerPath,
  insertionIndex: number
): StepGraphDropAssessment {
  const base = {
    sourcePath,
    targetContainerPath,
    insertionIndex
  }
  if (!isEditableStepPath(sourcePath)) {
    return {
      ...base,
      valid: false,
      operation: 'none',
      reason:
        parseStepStructurePath(sourcePath)?.kind === 'component-preview'
          ? '组件预览节点为只读，不能拖动。'
          : '只有可编辑步骤可以参与结构拖放。'
    }
  }

  try {
    const sourceContainerPath = getStepContainerPath(sourcePath)
    const source = parseEditablePath(sourcePath)
    const targetContainer = getReadonlyContainer(drafts, targetContainerPath)
    assertInsertionIndex(insertionIndex, targetContainer.length)

    if (sourceContainerPath === targetContainerPath) {
      const targetIndex = resolveReorderTargetIndex(
        source.childIndex,
        insertionIndex
      )
      if (targetIndex === source.childIndex) {
        return {
          ...base,
          valid: true,
          operation: 'none',
          reason: '步骤已位于该插入位置。'
        }
      }
      reorderStepDrafts(drafts, sourceContainerPath, source.childIndex, targetIndex)
      return {
        ...base,
        valid: true,
        operation: 'reorder',
        reason: ''
      }
    }

    moveStepDraft(drafts, sourcePath, targetContainerPath, insertionIndex)
    return {
      ...base,
      valid: true,
      operation: 'move',
      reason: ''
    }
  } catch (error: unknown) {
    return {
      ...base,
      valid: false,
      operation: 'none',
      reason:
        error instanceof StepGraphOperationError
          ? error.message
          : '当前步骤不能放置到该位置。'
    }
  }
}

export function assessStepDraftInsertion(
  drafts: readonly StepDraft[],
  step: StepDraft,
  targetContainerPath: StepContainerPath,
  insertionIndex: number
): StepGraphInsertionAssessment {
  try {
    const targetContainer = getReadonlyContainer(drafts, targetContainerPath)
    assertInsertionIndex(insertionIndex, targetContainer.length)
    assertContainerAcceptsStep(targetContainerPath, step)
    return {
      valid: true,
      reason: '',
      targetContainerPath,
      insertionIndex
    }
  } catch (error: unknown) {
    return {
      valid: false,
      reason:
        error instanceof StepGraphOperationError
          ? error.message
          : '当前步骤不能插入到该位置。',
      targetContainerPath,
      insertionIndex
    }
  }
}

export function moveStepDraftAtInsertion(
  drafts: readonly StepDraft[],
  sourcePath: EditableStepPath,
  targetContainerPath: StepContainerPath,
  insertionIndex: number
): StepGraphMutationResult<StepDraft> | null {
  const sourceContainerPath = getStepContainerPath(sourcePath)
  if (sourceContainerPath !== targetContainerPath) {
    return moveStepDraft(drafts, sourcePath, targetContainerPath, insertionIndex)
  }

  const source = parseEditablePath(sourcePath)
  const targetContainer = getReadonlyContainer(drafts, targetContainerPath)
  assertInsertionIndex(insertionIndex, targetContainer.length)
  const targetIndex = resolveReorderTargetIndex(source.childIndex, insertionIndex)
  if (targetIndex === source.childIndex) {
    return null
  }
  return reorderStepDrafts(
    drafts,
    sourceContainerPath,
    source.childIndex,
    targetIndex
  )
}

function resolveReorderTargetIndex(
  sourceIndex: number,
  insertionIndex: number
): number {
  return insertionIndex > sourceIndex ? insertionIndex - 1 : insertionIndex
}

export function duplicateStepDraft(
  drafts: readonly StepDraft[],
  sourcePath: EditableStepPath,
  targetContainerPath: StepContainerPath = getStepContainerPath(sourcePath),
  targetIndex?: number
): StepGraphMutationResult<StepDraft> {
  const source = parseEditablePath(sourcePath)
  const insertionIndex = targetIndex ?? source.childIndex + 1
  return insertStepDraft(
    drafts,
    targetContainerPath,
    insertionIndex,
    getStepAtPath(drafts, sourcePath)
  )
}

export function getStepDraftAtPath(
  drafts: readonly StepDraft[],
  path: EditableStepPath
): StepDraft {
  assertValidDraftStructure(drafts)
  return getStepAtPath(drafts, path)
}

export function getStepContainerLength(
  drafts: readonly StepDraft[],
  path: StepContainerPath
): number {
  assertValidDraftStructure(drafts)
  return getReadonlyContainer(drafts, path).length
}

export function deleteStepDraft(
  drafts: readonly StepDraft[],
  path: EditableStepPath
): StepGraphMutationResult<StepDraft> {
  assertValidDraftStructure(drafts)
  const containerPath = getStepContainerPath(path)
  const source = parseEditablePath(path)
  const sourceContainer = getReadonlyContainer(drafts, containerPath)
  assertExistingIndex(source.childIndex, sourceContainer.length)
  if (containerPath !== 'root' && sourceContainer.length === 1) {
    throw new StepGraphOperationError('EMPTY_BRANCH', '条件分支必须至少保留一个子步骤。')
  }

  const tree = cloneDraftTreeWithOrigins(drafts)
  const mutableContainer = getMutableContainer(tree.drafts, containerPath)
  mutableContainer.splice(source.childIndex, 1)
  normalizeStepNumbers(tree.drafts)
  const pathMigration = collectPathMigration(tree.drafts, tree.origins)
  const nextFocusIndex = Math.min(source.childIndex, mutableContainer.length - 1)

  return {
    drafts: tree.drafts,
    pathMigration,
    focusPath:
      nextFocusIndex >= 0 ? createChildPath(containerPath, nextFocusIndex) : null
  }
}

export function buildStepGraphWritePayloads(
  drafts: readonly StepDraft[]
): StepWritePayload[] {
  assertValidDraftStructure(drafts)
  return drafts.map((step: StepDraft, index: number): StepWritePayload =>
    buildStepWritePayload(step, index)
  )
}

export function migrateStepStructurePath(
  path: StepStructurePath,
  migration: StepPathMigration
): StepStructurePath | null {
  const exact = migration[path]
  if (exact) {
    return exact
  }

  const parsed = parseStepStructurePath(path)
  if (parsed?.kind !== 'component-preview') {
    return null
  }
  const oldTopPath = createTopStepPath(parsed.topIndex)
  const migratedTopPath = migration[oldTopPath]
  const migratedTop = migratedTopPath ? parseStepStructurePath(migratedTopPath) : null
  if (migratedTop?.kind !== 'top-step') {
    return null
  }
  return createComponentPreviewPath(migratedTop.topIndex, parsed.childIndex)
}

export function migrateStepGraphDisplayState(
  displayState: StepGraphDisplayState,
  migration: StepPathMigration
): StepGraphDisplayState {
  const nodeStates: Record<string, StepGraphNodeDisplayState> = {}
  for (const [path, state] of Object.entries(displayState.nodeStates)) {
    const parsedPath = parseStepStructurePath(path)
    if (!parsedPath) {
      continue
    }
    const migratedPath = migrateStepStructurePath(path as StepStructurePath, migration)
    if (migratedPath) {
      nodeStates[migratedPath] = deepClone(state)
    }
  }

  const annotations = displayState.annotations.flatMap(
    (annotation: StepGraphAnnotation): StepGraphAnnotation[] => {
      const source = migrateStepStructurePath(annotation.source, migration)
      const target = migrateStepStructurePath(annotation.target, migration)
      if (!source || !target || !isEditableStepPath(source) || !isEditableStepPath(target)) {
        return []
      }
      return [{ ...annotation, source, target }]
    }
  )

  return {
    nodeStates,
    annotations,
    connectionStyle: displayState.connectionStyle,
    background: deepClone(displayState.background)
  }
}

export function createDefaultStepGraphDisplayState(): StepGraphDisplayState {
  return {
    nodeStates: {},
    annotations: [],
    connectionStyle: 'bezier',
    background: {
      kind: 'grid'
    }
  }
}

function cloneDraftTreeWithOrigins(drafts: readonly StepDraft[]): ClonedDraftTree {
  const clonedDrafts = deepClone(drafts) as StepDraft[]
  const origins: CloneOrigins = {
    stepPaths: new WeakMap<StepDraft, EditableStepPath>(),
    branchPaths: new WeakMap<ConditionalBranchDraft, ConditionalBranchPath>(),
    elsePaths: new WeakMap<StepDraft, ElseBranchPath>()
  }

  drafts.forEach((sourceStep: StepDraft, topIndex: number): void => {
    const clonedStep = clonedDrafts[topIndex]
    origins.stepPaths.set(clonedStep, createTopStepPath(topIndex))
    if (sourceStep.type !== 'conditional_branch') {
      return
    }

    sourceStep.conditionalBranches.forEach(
      (sourceBranch: ConditionalBranchDraft, branchIndex: number): void => {
        const clonedBranch = clonedStep.conditionalBranches[branchIndex]
        origins.branchPaths.set(
          clonedBranch,
          createConditionalBranchPath(topIndex, sourceBranch.branchKey)
        )
        sourceBranch.steps.forEach((_sourceChild: StepDraft, childIndex: number): void => {
          origins.stepPaths.set(
            clonedBranch.steps[childIndex],
            createBranchChildPath(topIndex, sourceBranch.branchKey, childIndex)
          )
        })
      }
    )

    if (sourceStep.elseBranchEnabled) {
      origins.elsePaths.set(clonedStep, createElseBranchPath(topIndex))
      sourceStep.elseSteps.forEach((_sourceChild: StepDraft, childIndex: number): void => {
        origins.stepPaths.set(
          clonedStep.elseSteps[childIndex],
          createElseChildPath(topIndex, childIndex)
        )
      })
    }
  })

  return { drafts: clonedDrafts, origins }
}

function collectPathMigration(
  drafts: readonly StepDraft[],
  origins: CloneOrigins
): StepPathMigration {
  const migration: Record<string, StepStructurePath> = { root: 'root' }

  drafts.forEach((step: StepDraft, topIndex: number): void => {
    const topPath = createTopStepPath(topIndex)
    const oldTopPath = origins.stepPaths.get(step)
    if (oldTopPath) {
      migration[oldTopPath] = topPath
    }
    if (step.type !== 'conditional_branch') {
      return
    }

    step.conditionalBranches.forEach(
      (branch: ConditionalBranchDraft): void => {
        const branchPath = createConditionalBranchPath(topIndex, branch.branchKey)
        const oldBranchPath = origins.branchPaths.get(branch)
        if (oldBranchPath) {
          migration[oldBranchPath] = branchPath
        }
        branch.steps.forEach((childStep: StepDraft, childIndex: number): void => {
          const oldChildPath = origins.stepPaths.get(childStep)
          if (oldChildPath) {
            migration[oldChildPath] = createBranchChildPath(
              topIndex,
              branch.branchKey,
              childIndex
            )
          }
        })
      }
    )

    if (step.elseBranchEnabled) {
      const oldElsePath = origins.elsePaths.get(step)
      if (oldElsePath) {
        migration[oldElsePath] = createElseBranchPath(topIndex)
      }
      step.elseSteps.forEach((childStep: StepDraft, childIndex: number): void => {
        const oldChildPath = origins.stepPaths.get(childStep)
        if (oldChildPath) {
          migration[oldChildPath] = createElseChildPath(topIndex, childIndex)
        }
      })
    }
  })

  return migration
}

function getStepAtPath(drafts: readonly StepDraft[], path: EditableStepPath): StepDraft {
  const parsed = parseEditablePath(path)
  const container = getReadonlyContainer(drafts, getStepContainerPath(path))
  const step = container[parsed.childIndex]
  if (!step) {
    throw invalidPath(path)
  }
  return step
}

function getReadonlyContainer(
  drafts: readonly StepDraft[],
  path: StepContainerPath
): readonly StepDraft[] {
  return getContainer(drafts, path)
}

function getMutableContainer(drafts: StepDraft[], path: StepContainerPath): StepDraft[] {
  return getContainer(drafts, path)
}

function getContainer(drafts: StepDraft[], path: StepContainerPath): StepDraft[]
function getContainer(
  drafts: readonly StepDraft[],
  path: StepContainerPath
): readonly StepDraft[]
function getContainer(
  drafts: readonly StepDraft[] | StepDraft[],
  path: StepContainerPath
): readonly StepDraft[] | StepDraft[] {
  const parsed = parseStepStructurePath(path)
  if (parsed?.kind === 'root') {
    return drafts
  }
  if (parsed?.kind !== 'branch' && parsed?.kind !== 'else') {
    throw invalidPath(path)
  }

  const parent = drafts[parsed.topIndex]
  if (!parent || parent.type !== 'conditional_branch') {
    throw invalidPath(path)
  }
  if (parsed.kind === 'else') {
    if (!parent.elseBranchEnabled) {
      throw invalidPath(path)
    }
    return parent.elseSteps
  }

  const branch = parent.conditionalBranches.find(
    (item: ConditionalBranchDraft): boolean => item.branchKey === parsed.branchKey
  )
  if (!branch) {
    throw invalidPath(path)
  }
  return branch.steps
}

function parseEditablePath(
  path: EditableStepPath
): { containerPath: StepContainerPath; childIndex: number } {
  const parsed = parseStepStructurePath(path)
  if (parsed?.kind === 'top-step') {
    return { containerPath: 'root', childIndex: parsed.topIndex }
  }
  if (parsed?.kind === 'branch-child') {
    return {
      containerPath: createConditionalBranchPath(parsed.topIndex, parsed.branchKey),
      childIndex: parsed.childIndex
    }
  }
  if (parsed?.kind === 'else-child') {
    return {
      containerPath: createElseBranchPath(parsed.topIndex),
      childIndex: parsed.childIndex
    }
  }
  if (parsed?.kind === 'component-preview') {
    throw new StepGraphOperationError('READ_ONLY_PATH', '组件预览步骤为只读节点。')
  }
  throw invalidPath(path)
}

function createChildPath(containerPath: StepContainerPath, index: number): EditableStepPath {
  if (containerPath === 'root') {
    return createTopStepPath(index)
  }
  const parsed = parseStepStructurePath(containerPath)
  if (parsed?.kind === 'branch') {
    return createBranchChildPath(parsed.topIndex, parsed.branchKey, index)
  }
  if (parsed?.kind === 'else') {
    return createElseChildPath(parsed.topIndex, index)
  }
  throw invalidPath(containerPath)
}

function adjustContainerAfterTopRemoval(
  targetPath: StepContainerPath,
  sourceContainerPath: StepContainerPath,
  sourceIndex: number
): StepContainerPath {
  if (sourceContainerPath !== 'root' || targetPath === 'root') {
    return targetPath
  }
  const parsed = parseStepStructurePath(targetPath)
  if (!parsed || parsed.kind === 'root') {
    return targetPath
  }
  if (parsed.topIndex === sourceIndex) {
    throw new StepGraphOperationError(
      'INVALID_NESTING',
      '不能将步骤移动到自身包含的分支。'
    )
  }
  if (parsed.topIndex < sourceIndex) {
    return targetPath
  }
  if (parsed.kind === 'branch') {
    return createConditionalBranchPath(parsed.topIndex - 1, parsed.branchKey)
  }
  if (parsed.kind === 'else') {
    return createElseBranchPath(parsed.topIndex - 1)
  }
  throw invalidPath(targetPath)
}

function assertContainerAcceptsStep(
  containerPath: StepContainerPath,
  step: StepDraft
): void {
  if (
    containerPath !== 'root' &&
    (step.type === 'component_call' || step.type === 'conditional_branch')
  ) {
    throw new StepGraphOperationError(
      'INVALID_NESTING',
      '分支子步骤不支持 component_call 或 conditional_branch。'
    )
  }
}

function assertValidDraftStructure(drafts: readonly StepDraft[]): void {
  drafts.forEach((step: StepDraft): void => {
    if (step.type !== 'conditional_branch') {
      return
    }
    if (step.conditionalBranches.length === 0) {
      throw new StepGraphOperationError(
        'EMPTY_BRANCH',
        '条件分支步骤必须至少包含一个条件分支。'
      )
    }
    const branchKeys = new Set<string>()
    step.conditionalBranches.forEach((branch: ConditionalBranchDraft): void => {
      if (!branch.branchKey.trim() || branchKeys.has(branch.branchKey)) {
        throw new StepGraphOperationError(
          'INVALID_PATH',
          '条件分支 branchKey 必须非空且在父步骤内唯一。'
        )
      }
      branchKeys.add(branch.branchKey)
      assertNonEmptyBranch(branch.steps)
      branch.steps.forEach(assertLegalBranchChild)
    })
    if (step.elseBranchEnabled) {
      assertNonEmptyBranch(step.elseSteps)
      step.elseSteps.forEach(assertLegalBranchChild)
    }
  })
}

function assertNonEmptyBranch(steps: readonly StepDraft[]): void {
  if (steps.length === 0) {
    throw new StepGraphOperationError('EMPTY_BRANCH', '条件分支必须至少包含一个子步骤。')
  }
}

function assertLegalBranchChild(step: StepDraft): void {
  if (step.type === 'component_call' || step.type === 'conditional_branch') {
    throw new StepGraphOperationError(
      'INVALID_NESTING',
      '分支子步骤不支持 component_call 或 conditional_branch。'
    )
  }
}

function normalizeStepNumbers(drafts: StepDraft[]): void {
  drafts.forEach((step: StepDraft, topIndex: number): void => {
    step.stepNo = topIndex + 1
    step.conditionalBranches.forEach((branch: ConditionalBranchDraft): void => {
      branch.steps.forEach((childStep: StepDraft, childIndex: number): void => {
        childStep.stepNo = childIndex + 1
      })
    })
    step.elseSteps.forEach((childStep: StepDraft, childIndex: number): void => {
      childStep.stepNo = childIndex + 1
    })
  })
}

function deepClone<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item: unknown): unknown => deepClone(item)) as T
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]: [string, unknown]): [string, unknown] => [
        key,
        deepClone(item)
      ])
    ) as T
  }
  return value
}

function assertNonNegativeIndex(index: number): void {
  if (!Number.isInteger(index) || index < 0) {
    throw new StepGraphOperationError('INVALID_INDEX', '索引必须是非负整数。')
  }
}

function assertInsertionIndex(index: number, length: number): void {
  assertNonNegativeIndex(index)
  if (index > length) {
    throw new StepGraphOperationError('INVALID_INDEX', '插入索引超出目标列表范围。')
  }
}

function assertExistingIndex(index: number, length: number): void {
  assertNonNegativeIndex(index)
  if (index >= length) {
    throw new StepGraphOperationError('INVALID_INDEX', '步骤索引超出列表范围。')
  }
}

function invalidPath(path: string): StepGraphOperationError {
  return new StepGraphOperationError('INVALID_PATH', `无效的步骤结构路径：${path}`)
}
