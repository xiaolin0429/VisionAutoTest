import type {
  StepGraph,
  StepGraphAnnotation,
  StepGraphDisplayState,
  StepGraphEdge,
  StepGraphNode,
  StepGraphProjectionOptions,
  StepPathMigration,
  StepStructurePath,
  TopStepPath
} from '@/types/stepGraph'
import {
  applyStepGraphDisplayState,
  createTopStepPath,
  filterCollapsedStepGraph,
  layoutStepGraph,
  parseStepStructurePath,
  projectStepDraftsToGraph
} from '@/utils/stepGraph'
import type { StepDraft } from '@/utils/steps'

export interface StepGraphIncrementalDependencies {
  projectGraph?: (
    drafts: readonly StepDraft[],
    options: StepGraphProjectionOptions
  ) => StepGraph
  layoutGraph?: (graph: StepGraph) => StepGraph
  projectTopLevel?: (
    draft: StepDraft,
    topIndex: number,
    options: StepGraphProjectionOptions
  ) => StepGraph
  layoutTopLevel?: (
    graph: StepGraph,
    topIndex: number
  ) => StepGraph
}

export interface StepGraphIncrementalResult {
  projectedGraph: StepGraph
  canvasGraph: StepGraph
  affectedTopPaths: readonly TopStepPath[]
  projectedTopPaths: readonly TopStepPath[]
  laidOutTopPaths: readonly TopStepPath[]
}

export interface StepGraphIncrementalPipeline {
  initialize: (
    drafts: readonly StepDraft[],
    options: StepGraphProjectionOptions,
    displayState: StepGraphDisplayState
  ) => StepGraphIncrementalResult
  updateStructure: (
    drafts: readonly StepDraft[],
    pathMigration: StepPathMigration,
    options: StepGraphProjectionOptions,
    displayState: StepGraphDisplayState
  ) => StepGraphIncrementalResult
}

interface TopSubgraph {
  path: TopStepPath
  graph: StepGraph
}

function cloneDrafts(drafts: readonly StepDraft[]): StepDraft[] {
  return JSON.parse(JSON.stringify(drafts)) as StepDraft[]
}

function draftSignature(draft: StepDraft): string {
  return JSON.stringify(draft, (key: string, value: unknown): unknown =>
    key === 'stepNo' ? undefined : value
  )
}

function getTopPath(path: StepStructurePath): TopStepPath | null {
  const parsed = parseStepStructurePath(path)
  return parsed && parsed.kind !== 'root'
    ? createTopStepPath(parsed.topIndex)
    : null
}

function extractTopSubgraphs(graph: StepGraph): Map<TopStepPath, TopSubgraph> {
  const nodesByTop = new Map<TopStepPath, StepGraphNode[]>()
  graph.nodes.forEach((node: StepGraphNode): void => {
    const topPath = getTopPath(node.path)
    if (topPath) {
      nodesByTop.set(topPath, [...(nodesByTop.get(topPath) ?? []), node])
    }
  })

  const result = new Map<TopStepPath, TopSubgraph>()
  nodesByTop.forEach((nodes: StepGraphNode[], path: TopStepPath): void => {
    const paths = new Set(
      nodes.map((node: StepGraphNode): StepStructurePath => node.path)
    )
    result.set(path, {
      path,
      graph: {
        nodes,
        edges: graph.edges.filter(
          (edge: StepGraphEdge): boolean =>
            paths.has(edge.source) &&
            paths.has(edge.target) &&
            !edge.annotationOnly
        )
      }
    })
  })
  return result
}

function replaceTopPrefix(
  path: StepStructurePath,
  oldTopPath: TopStepPath,
  nextTopPath: TopStepPath
): StepStructurePath {
  if (path === oldTopPath) {
    return nextTopPath
  }
  if (path.startsWith(`${oldTopPath}:`)) {
    return `${nextTopPath}${path.slice(oldTopPath.length)}` as StepStructurePath
  }
  return path
}

function rebaseTopSubgraph(
  subgraph: TopSubgraph,
  nextPath: TopStepPath,
  draft: StepDraft,
  topIndex: number
): TopSubgraph {
  const oldPath = subgraph.path
  if (oldPath === nextPath) {
    return subgraph
  }
  subgraph.graph.nodes.forEach((node: StepGraphNode): void => {
    node.path = replaceTopPrefix(node.path, oldPath, nextPath)
    node.id = node.path
    if (node.parentPath && node.parentPath !== 'root') {
      node.parentPath = replaceTopPrefix(node.parentPath, oldPath, nextPath)
    }
    if (node.kind === 'top-step') {
      node.order = topIndex
      node.stepNo = topIndex + 1
      if (!draft.name.trim()) {
        node.label = `${node.typeLabel} ${topIndex + 1}`
      }
    }
  })
  subgraph.graph.edges.forEach((edge: StepGraphEdge): void => {
    edge.source = replaceTopPrefix(edge.source, oldPath, nextPath)
    edge.target = replaceTopPrefix(edge.target, oldPath, nextPath)
    edge.id = `${edge.kind}:${edge.source}->${edge.target}`
  })
  subgraph.path = nextPath
  return subgraph
}

export function projectStepDraftTopLevelSubgraph(
  draft: StepDraft,
  topIndex: number,
  options: StepGraphProjectionOptions
): StepGraph {
  const graph = projectStepDraftsToGraph([draft], {
    rootLabel: options.rootLabel,
    componentPreviews: options.componentPreviews
  })
  const subgraph: TopSubgraph = {
    path: 'top:0',
    graph: {
      nodes: graph.nodes.filter(
        (node: StepGraphNode): boolean => node.path !== 'root'
      ),
      edges: graph.edges.filter(
        (edge: StepGraphEdge): boolean =>
          edge.source !== 'root' && !edge.annotationOnly
      )
    }
  }
  return rebaseTopSubgraph(
    subgraph,
    createTopStepPath(topIndex),
    draft,
    topIndex
  ).graph
}

function buildCanvasTopLevel(
  graph: StepGraph,
  topIndex: number,
  displayState: StepGraphDisplayState,
  layoutTopLevel: NonNullable<StepGraphIncrementalDependencies['layoutTopLevel']>
): StepGraph {
  const dimensioned = applyStepGraphDisplayState(graph, displayState)
  const visible = filterCollapsedStepGraph(dimensioned, displayState)
  return applyStepGraphDisplayState(
    layoutTopLevel(visible, topIndex),
    displayState
  )
}

function resolveRankSlots(
  previousCanvas: StepGraph,
  nextCount: number
): { x: number[]; y: number[] } {
  const previousTopNodes = previousCanvas.nodes
    .filter((node: StepGraphNode): boolean => node.kind === 'top-step')
    .sort((left: StepGraphNode, right: StepGraphNode): number =>
      left.order - right.order
    )
  const root = previousCanvas.nodes.find(
    (node: StepGraphNode): boolean => node.kind === 'root'
  )
  const fallbackX = previousTopNodes[0]?.position.x ?? root?.position.x ?? 24
  const firstY =
    previousTopNodes[0]?.position.y ??
    ((root?.position.y ?? 0) + (root?.height ?? 96) + 96)
  const gaps = previousTopNodes.slice(1).map(
    (node: StepGraphNode, index: number): number =>
      node.position.y - previousTopNodes[index].position.y
  )
  const rankGap =
    gaps.length > 0
      ? gaps.reduce((total: number, gap: number): number => total + gap, 0) /
        gaps.length
      : 192
  return {
    x: Array.from(
      { length: nextCount },
      (_value: unknown, index: number): number =>
        previousTopNodes[index]?.position.x ?? fallbackX
    ),
    y: Array.from(
      { length: nextCount },
      (_value: unknown, index: number): number => firstY + rankGap * index
    )
  }
}

function alignTopSubgraph(
  subgraph: TopSubgraph,
  topIndex: number,
  slots: { x: number[]; y: number[] },
  displayState: StepGraphDisplayState
): void {
  const topNode = subgraph.graph.nodes.find(
    (node: StepGraphNode): boolean => node.kind === 'top-step'
  )
  if (!topNode) {
    return
  }
  const deltaX = slots.x[topIndex] - topNode.position.x
  const deltaY = slots.y[topIndex] - topNode.position.y
  if (deltaX === 0 && deltaY === 0) {
    return
  }
  subgraph.graph.nodes.forEach((node: StepGraphNode): void => {
    if (displayState.nodeStates[node.path]?.position) {
      return
    }
    node.position = {
      x: node.position.x + deltaX,
      y: node.position.y + deltaY
    }
  })
}

function createSequenceEdges(
  topPaths: readonly TopStepPath[],
  previousGraph: StepGraph
): StepGraphEdge[] {
  const previousById = new Map(
    previousGraph.edges.map(
      (edge: StepGraphEdge): [string, StepGraphEdge] => [edge.id, edge]
    )
  )
  return topPaths.map(
    (target: TopStepPath, index: number): StepGraphEdge => {
      const source = index === 0 ? 'root' : topPaths[index - 1]
      const id = `sequence:${source}->${target}`
      return previousById.get(id) ?? {
        id,
        source,
        target,
        kind: 'sequence',
        label: index === 0 ? '开始' : '顺序执行',
        executable: true,
        annotationOnly: false
      }
    }
  )
}

function createAnnotationEdges(
  options: StepGraphProjectionOptions,
  visiblePaths: ReadonlySet<StepStructurePath>,
  previousGraph: StepGraph
): StepGraphEdge[] {
  const previousById = new Map(
    previousGraph.edges.map(
      (edge: StepGraphEdge): [string, StepGraphEdge] => [edge.id, edge]
    )
  )
  return (options.annotations ?? []).flatMap(
    (annotation: StepGraphAnnotation): StepGraphEdge[] => {
      if (
        !visiblePaths.has(annotation.source) ||
        !visiblePaths.has(annotation.target)
      ) {
        return []
      }
      const id = `annotation:${annotation.id}`
      const kind =
        annotation.kind === 'dependency'
          ? 'dependency-annotation'
          : 'parallel-annotation'
      const label = `${annotation.label?.trim() || (
        annotation.kind === 'dependency' ? '依赖' : '并行'
      )} · 仅标注`
      const previous = previousById.get(id)
      if (
        previous &&
        previous.source === annotation.source &&
        previous.target === annotation.target &&
        previous.kind === kind &&
        previous.label === label
      ) {
        return [previous]
      }
      return [{
        id,
        source: annotation.source,
        target: annotation.target,
        kind,
        label,
        executable: false,
        annotationOnly: true
      }]
    }
  )
}

function updateRootNode(
  previousGraph: StepGraph,
  drafts: readonly StepDraft[],
  options: StepGraphProjectionOptions
): StepGraphNode {
  const root = previousGraph.nodes.find(
    (node: StepGraphNode): boolean => node.kind === 'root'
  ) ?? projectStepDraftsToGraph([], options).nodes[0]
  root.label = options.rootLabel?.trim() || '用例根节点'
  root.detail = `${drafts.length} 个顶层步骤`
  root.summary = root.detail
  return root
}

function assembleGraph(
  root: StepGraphNode,
  subgraphs: readonly TopSubgraph[],
  previousGraph: StepGraph,
  options: StepGraphProjectionOptions
): StepGraph {
  const topPaths = subgraphs.map(
    (subgraph: TopSubgraph): TopStepPath => subgraph.path
  )
  const nodes = [
    root,
    ...subgraphs.flatMap(
      (subgraph: TopSubgraph): StepGraphNode[] => subgraph.graph.nodes
    )
  ]
  const visiblePaths = new Set(
    nodes.map((node: StepGraphNode): StepStructurePath => node.path)
  )
  return {
    nodes,
    edges: [
      ...createSequenceEdges(topPaths, previousGraph),
      ...subgraphs.flatMap(
        (subgraph: TopSubgraph): StepGraphEdge[] => subgraph.graph.edges
      ),
      ...createAnnotationEdges(options, visiblePaths, previousGraph)
    ]
  }
}

export function createStepGraphIncrementalPipeline(
  dependencies: StepGraphIncrementalDependencies = {}
): StepGraphIncrementalPipeline {
  const projectGraph = dependencies.projectGraph ?? projectStepDraftsToGraph
  const layoutGraph = dependencies.layoutGraph ?? layoutStepGraph
  const projectTopLevel =
    dependencies.projectTopLevel ?? projectStepDraftTopLevelSubgraph
  const layoutTopLevel =
    dependencies.layoutTopLevel ??
    ((graph: StepGraph): StepGraph => layoutStepGraph(graph))
  let previousDrafts: StepDraft[] = []
  let current: StepGraphIncrementalResult = {
    projectedGraph: { nodes: [], edges: [] },
    canvasGraph: { nodes: [], edges: [] },
    affectedTopPaths: [],
    projectedTopPaths: [],
    laidOutTopPaths: []
  }

  function initialize(
    drafts: readonly StepDraft[],
    options: StepGraphProjectionOptions,
    displayState: StepGraphDisplayState
  ): StepGraphIncrementalResult {
    const projectedGraph = projectGraph(drafts, options)
    const dimensioned = applyStepGraphDisplayState(projectedGraph, displayState)
    const visible = filterCollapsedStepGraph(dimensioned, displayState)
    const canvasGraph = applyStepGraphDisplayState(
      layoutGraph(visible),
      displayState
    )
    const topPaths = drafts.map(
      (_draft: StepDraft, index: number): TopStepPath =>
        createTopStepPath(index)
    )
    previousDrafts = cloneDrafts(drafts)
    current = {
      projectedGraph,
      canvasGraph,
      affectedTopPaths: topPaths,
      projectedTopPaths: topPaths,
      laidOutTopPaths: topPaths
    }
    return current
  }

  function updateStructure(
    drafts: readonly StepDraft[],
    pathMigration: StepPathMigration,
    options: StepGraphProjectionOptions,
    displayState: StepGraphDisplayState
  ): StepGraphIncrementalResult {
    if (current.projectedGraph.nodes.length === 0) {
      return initialize(drafts, options, displayState)
    }
    const previousProjected = extractTopSubgraphs(current.projectedGraph)
    const previousCanvas = extractTopSubgraphs(current.canvasGraph)
    const oldPathByNextPath = new Map<TopStepPath, TopStepPath>()
    previousDrafts.forEach((_draft: StepDraft, oldIndex: number): void => {
      const oldPath = createTopStepPath(oldIndex)
      const nextPath = pathMigration[oldPath]
      if (nextPath && parseStepStructurePath(nextPath)?.kind === 'top-step') {
        oldPathByNextPath.set(nextPath as TopStepPath, oldPath)
      }
    })
    const slots = resolveRankSlots(current.canvasGraph, drafts.length)
    const projectedSubgraphs: TopSubgraph[] = []
    const canvasSubgraphs: TopSubgraph[] = []
    const affected = new Set<TopStepPath>()
    const projectedPaths: TopStepPath[] = []
    const laidOutPaths: TopStepPath[] = []

    drafts.forEach((draft: StepDraft, topIndex: number): void => {
      const nextPath = createTopStepPath(topIndex)
      const oldPath = oldPathByNextPath.get(nextPath)
      const oldParsed = oldPath ? parseStepStructurePath(oldPath) : null
      const oldDraft =
        oldParsed?.kind === 'top-step'
          ? previousDrafts[oldParsed.topIndex]
          : undefined
      const reusable =
        oldPath !== undefined &&
        oldDraft !== undefined &&
        draftSignature(oldDraft) === draftSignature(draft) &&
        previousProjected.has(oldPath) &&
        previousCanvas.has(oldPath)

      let projectedSubgraph: TopSubgraph
      let canvasSubgraph: TopSubgraph
      if (reusable && oldPath) {
        projectedSubgraph = rebaseTopSubgraph(
          previousProjected.get(oldPath) as TopSubgraph,
          nextPath,
          draft,
          topIndex
        )
        canvasSubgraph = rebaseTopSubgraph(
          previousCanvas.get(oldPath) as TopSubgraph,
          nextPath,
          draft,
          topIndex
        )
      } else {
        affected.add(nextPath)
        projectedPaths.push(nextPath)
        laidOutPaths.push(nextPath)
        projectedSubgraph = {
          path: nextPath,
          graph: projectTopLevel(draft, topIndex, options)
        }
        canvasSubgraph = {
          path: nextPath,
          graph: buildCanvasTopLevel(
            projectedSubgraph.graph,
            topIndex,
            displayState,
            layoutTopLevel
          )
        }
      }
      alignTopSubgraph(canvasSubgraph, topIndex, slots, displayState)
      projectedSubgraphs.push(projectedSubgraph)
      canvasSubgraphs.push(canvasSubgraph)
    })

    previousDrafts.forEach((_draft: StepDraft, oldIndex: number): void => {
      const oldPath = createTopStepPath(oldIndex)
      if (!pathMigration[oldPath]) {
        affected.add(oldPath)
      }
    })

    const projectedRoot = updateRootNode(
      current.projectedGraph,
      drafts,
      options
    )
    const projectedGraph = assembleGraph(
      projectedRoot,
      projectedSubgraphs,
      current.projectedGraph,
      options
    )
    let canvasGraph: StepGraph
    if (displayState.nodeStates.root?.collapsed === true) {
      const canvasRoot = updateRootNode(current.canvasGraph, drafts, options)
      canvasRoot.hiddenDescendantCount = projectedGraph.nodes.length - 1
      canvasGraph = { nodes: [canvasRoot], edges: [] }
    } else {
      const canvasRoot = updateRootNode(current.canvasGraph, drafts, options)
      canvasRoot.hiddenDescendantCount = 0
      canvasGraph = assembleGraph(
        canvasRoot,
        canvasSubgraphs,
        current.canvasGraph,
        options
      )
    }
    previousDrafts = cloneDrafts(drafts)
    current = {
      projectedGraph,
      canvasGraph,
      affectedTopPaths: [...affected],
      projectedTopPaths: projectedPaths,
      laidOutTopPaths: laidOutPaths
    }
    return current
  }

  return { initialize, updateStructure }
}
