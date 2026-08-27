import { describe, expect, it } from 'vitest'

import type { StepType, StepWritePayload } from '@/types/models'
import type {
  EditableStepPath,
  StepGraphComponentPreview,
  StepGraphDisplayState,
  StepGraphEdge,
  StepGraphEdgeKind,
  StepGraphNode
} from '@/types/stepGraph'
import {
  assessStepDraftDrop,
  applyStepGraphDisplayState,
  buildStepGraphWritePayloads,
  createBranchChildPath,
  createComponentPreviewPath,
  createConditionalBranchPath,
  createDefaultStepGraphDisplayState,
  createElseBranchPath,
  createElseChildPath,
  createTopStepPath,
  deleteStepDraft,
  duplicateStepDraft,
  filterCollapsedStepGraph,
  getStepGraphEdgeVisual,
  insertStepDraft,
  isEditableStepPath,
  layoutStepGraph,
  migrateStepGraphDisplayState,
  moveStepDraft,
  moveStepDraftAtInsertion,
  parseStepStructurePath,
  projectStepDraftsToGraph,
  reorderStepDrafts,
  shouldShowStepGraphEdgeLabels,
  StepGraphOperationError
} from '@/utils/stepGraph'
import {
  createBranchChildStepDraft,
  createEmptyStepDraft,
  createOcrTargetDraft,
  type ConditionalBranchDraft,
  type StepDraft
} from '@/utils/steps'

function makeStep(type: StepType, name: string, id: number): StepDraft {
  const step = createEmptyStepDraft(0)
  step.id = id
  step.name = name
  step.type = type
  if (type === 'component_call') {
    step.componentId = 42
  }
  if (type === 'click') {
    step.selector = '#submit'
  }
  return step
}

function makeBranch(
  branchKey: string,
  branchName: string,
  steps: StepDraft[]
): ConditionalBranchDraft {
  return {
    id: 100,
    branchKey,
    branchName,
    conditionType: 'selector_exists',
    ocrTarget: createOcrTargetDraft(),
    templateId: null,
    threshold: null,
    selector: '#ready',
    steps
  }
}

function makeConditionalStep(
  name: string,
  branches: ConditionalBranchDraft[],
  elseSteps: StepDraft[] = []
): StepDraft {
  const step = makeStep('conditional_branch', name, 20)
  step.conditionalBranches = branches
  step.elseBranchEnabled = elseSteps.length > 0
  step.elseBranchName = '兜底'
  step.elseSteps = elseSteps
  return step
}

function makeProjectionDrafts(): StepDraft[] {
  const navigate = makeStep('navigate', '打开登录页', 7)
  navigate.url = '/login'
  const conditional = makeConditionalStep(
    '判断登录状态',
    [
      makeBranch('happy:path', '已登录', [
        makeStep('click', '进入工作台', 7),
        makeStep('wait', '等待稳定', 7)
      ])
    ],
    [makeStep('input', '输入账号', 7)]
  )
  return [navigate, conditional, makeStep('component_call', '执行登录组件', 7)]
}

function makeComponentPreview(): StepGraphComponentPreview {
  return {
    componentId: 42,
    name: '登录组件',
    status: 'published',
    steps: [
      { name: '输入密码', type: 'input' },
      { name: '点击登录', type: 'click' }
    ]
  }
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value as Record<string, unknown>).forEach((item: unknown): void => {
      deepFreeze(item)
    })
    Object.freeze(value)
  }
  return value
}

function expectOperationError(action: () => unknown, code: StepGraphOperationError['code']): void {
  try {
    action()
    throw new Error('Expected StepGraphOperationError')
  } catch (error: unknown) {
    expect(error).toBeInstanceOf(StepGraphOperationError)
    expect((error as StepGraphOperationError).code).toBe(code)
  }
}

function getNode(graphNodes: readonly StepGraphNode[], path: string): StepGraphNode {
  const node = graphNodes.find((item: StepGraphNode): boolean => item.path === path)
  if (!node) {
    throw new Error(`Missing graph node: ${path}`)
  }
  return node
}

describe('step graph structure paths', (): void => {
  it('builds and parses deterministic paths without draft ids', (): void => {
    const branchPath = createConditionalBranchPath(2, 'ready:mobile')
    const childPath = createBranchChildPath(2, 'ready:mobile', 3)

    expect(createTopStepPath(2)).toBe('top:2')
    expect(branchPath).toBe('top:2:branch:ready%3Amobile')
    expect(childPath).toBe('top:2:branch:ready%3Amobile:child:3')
    expect(createElseBranchPath(2)).toBe('top:2:else')
    expect(createElseChildPath(2, 1)).toBe('top:2:else:child:1')
    expect(createComponentPreviewPath(2, 4)).toBe('top:2:component:child:4')
    expect(parseStepStructurePath(childPath)).toEqual({
      kind: 'branch-child',
      topIndex: 2,
      branchKey: 'ready:mobile',
      childIndex: 3
    })
    expect(isEditableStepPath(childPath)).toBe(true)
    expect(isEditableStepPath(createComponentPreviewPath(2, 4))).toBe(false)
  })
})

describe('step graph projection and layout', (): void => {
  it('projects top order, branches, else, component preview, and annotation edges', (): void => {
    const drafts = deepFreeze(makeProjectionDrafts())
    const branchChildPath = createBranchChildPath(1, 'happy:path', 0)
    const graph = projectStepDraftsToGraph(drafts, {
      rootLabel: '登录用例',
      componentPreviews: { 42: makeComponentPreview() },
      annotations: [
        {
          id: 'dependency-1',
          source: createTopStepPath(0),
          target: branchChildPath,
          kind: 'dependency'
        },
        {
          id: 'parallel-1',
          source: branchChildPath,
          target: createTopStepPath(2),
          kind: 'parallel',
          label: '可并行准备'
        }
      ]
    })

    expect(graph.nodes.map((node: StepGraphNode): string => node.path)).toEqual([
      'root',
      'top:0',
      'top:1',
      'top:1:branch:happy%3Apath',
      'top:1:branch:happy%3Apath:child:0',
      'top:1:branch:happy%3Apath:child:1',
      'top:1:else',
      'top:1:else:child:0',
      'top:2',
      'top:2:component:child:0',
      'top:2:component:child:1'
    ])
    expect(
      graph.edges
        .filter((edge: StepGraphEdge): boolean => edge.kind === 'sequence')
        .map((edge: StepGraphEdge): string => `${edge.source}->${edge.target}`)
    ).toContain('top:0->top:1')
    expect(getNode(graph.nodes, 'top:1:else').order).toBe(1)
    expect(getNode(graph.nodes, 'top:2:component:child:0')).toMatchObject({
      readOnly: true,
      editable: false,
      componentId: 42,
      componentStatus: 'published'
    })
    expect(graph.edges.filter((edge: StepGraphEdge): boolean => edge.annotationOnly)).toEqual([
      expect.objectContaining({
        kind: 'dependency-annotation',
        label: '依赖 · 仅标注',
        executable: false
      }),
      expect.objectContaining({
        kind: 'parallel-annotation',
        label: '可并行准备 · 仅标注',
        executable: false
      })
    ])
  })

  it('filters collapsed descendants and reports the hidden subtree size', (): void => {
    const graph = deepFreeze(
      projectStepDraftsToGraph(makeProjectionDrafts(), {
        componentPreviews: { 42: makeComponentPreview() }
      })
    )
    const displayState = createDefaultStepGraphDisplayState()
    displayState.nodeStates['top:1'] = { collapsed: true }
    const filtered = filterCollapsedStepGraph(graph, displayState)

    expect(filtered.nodes.map((node: StepGraphNode): string => node.path)).not.toContain(
      'top:1:branch:happy%3Apath'
    )
    expect(getNode(filtered.nodes, 'top:1').hiddenDescendantCount).toBe(5)
    expect(
      filtered.edges.some(
        (edge: StepGraphEdge): boolean =>
          edge.source === 'top:1' && edge.target === 'top:2'
      )
    ).toBe(true)
  })

  it('projects select_option OCR targets into the canvas summary', (): void => {
    const select = makeStep('select_option', '选择国家', 10)
    select.fieldTarget = createOcrTargetDraft({
      text: '国家/地区',
      role: 'input'
    })
    select.optionTarget = createOcrTargetDraft({
      text: '中国',
      role: 'menu_item'
    })

    const graph = projectStepDraftsToGraph([select])

    expect(getNode(graph.nodes, 'top:0')).toMatchObject({
      detail: 'OCR 选择',
      summary: 'OCR 选择 国家/地区 → 中国',
      errorCount: 0
    })
  })

  it('produces deterministic top-to-bottom Dagre positions without annotation influence', (): void => {
    const drafts = [
      makeStep('wait', '一', 1),
      makeStep('click', '二', 1),
      makeStep('wait', '三', 1)
    ]
    const baseGraph = projectStepDraftsToGraph(drafts)
    const annotatedGraph = projectStepDraftsToGraph(drafts, {
      annotations: [
        {
          id: 'back-link',
          source: createTopStepPath(2),
          target: createTopStepPath(0),
          kind: 'dependency'
        }
      ]
    })

    const firstLayout = layoutStepGraph(deepFreeze(baseGraph))
    const secondLayout = layoutStepGraph(deepFreeze(baseGraph))
    const annotatedLayout = layoutStepGraph(deepFreeze(annotatedGraph))
    const positions = firstLayout.nodes.map((node: StepGraphNode) => node.position)

    expect(secondLayout.nodes.map((node: StepGraphNode) => node.position)).toEqual(positions)
    expect(annotatedLayout.nodes.map((node: StepGraphNode) => node.position)).toEqual(positions)
    expect(getNode(firstLayout.nodes, 'root').position.y).toBeLessThan(
      getNode(firstLayout.nodes, 'top:0').position.y
    )
    expect(getNode(firstLayout.nodes, 'top:0').position.y).toBeLessThan(
      getNode(firstLayout.nodes, 'top:1').position.y
    )
    expect(getNode(firstLayout.nodes, 'top:1').position.y).toBeLessThan(
      getNode(firstLayout.nodes, 'top:2').position.y
    )
  })
})

describe('step graph edge and zoom semantics', (): void => {
  it('keeps execution and annotation relationships visually distinct', (): void => {
    const expected: Record<
      StepGraphEdgeKind,
      {
        color: string
        dasharray: string | null
        arrow: 'closed' | 'open' | 'none'
        doubleTrack: boolean
      }
    > = {
      sequence: {
        color: '#475569',
        dasharray: null,
        arrow: 'closed',
        doubleTrack: false
      },
      condition: {
        color: '#d97706',
        dasharray: null,
        arrow: 'closed',
        doubleTrack: false
      },
      else: {
        color: '#64748b',
        dasharray: '7 5',
        arrow: 'closed',
        doubleTrack: false
      },
      component: {
        color: '#4f46e5',
        dasharray: '2 5',
        arrow: 'closed',
        doubleTrack: false
      },
      'dependency-annotation': {
        color: '#64748b',
        dasharray: '7 5',
        arrow: 'open',
        doubleTrack: false
      },
      'parallel-annotation': {
        color: '#0891b2',
        dasharray: '7 5',
        arrow: 'none',
        doubleTrack: true
      }
    }

    Object.entries(expected).forEach(([kind, visual]): void => {
      expect(getStepGraphEdgeVisual(kind as StepGraphEdgeKind)).toEqual(visual)
    })
  })

  it('hides labels below 60 percent zoom and restores them at the boundary', (): void => {
    expect(shouldShowStepGraphEdgeLabels(0.599)).toBe(false)
    expect(shouldShowStepGraphEdgeLabels(0.6)).toBe(true)
    expect(shouldShowStepGraphEdgeLabels(1)).toBe(true)
  })

  it('projects stable node summaries, runtime metadata, and error counts', (): void => {
    const invalidClick = makeStep('click', '提交', 1)
    invalidClick.selector = ''
    invalidClick.timeoutMs = 3200
    invalidClick.retryTimes = 2
    const graph = projectStepDraftsToGraph([invalidClick])

    expect(getNode(graph.nodes, 'top:0')).toMatchObject({
      typeLabel: '点击',
      summary: '点击 --',
      timeoutMs: 3200,
      retryTimes: 2,
      errorCount: 1
    })
  })

  it('keeps invalid branch keys visible through editor-only fallback paths', (): void => {
    const conditional = makeConditionalStep('待修正条件', [
      makeBranch('', '分支一', [makeStep('wait', 'A', 1)]),
      makeBranch('', '分支二', [makeStep('wait', 'B', 2)])
    ])
    const graph = projectStepDraftsToGraph([conditional])
    const lanePaths = graph.nodes
      .filter((node: StepGraphNode): boolean => node.kind === 'branch-lane')
      .map((node: StepGraphNode): string => node.path)

    expect(new Set(lanePaths).size).toBe(2)
    expect(lanePaths.every((path: string): boolean => path.includes('__draft_'))).toBe(true)
    expect(getNode(graph.nodes, 'top:0').errorCount).toBeGreaterThan(0)
  })
})

describe('step graph collapse behavior', (): void => {
  it('collapses a single branch lane without hiding sibling lanes', (): void => {
    const conditional = makeConditionalStep(
      '条件',
      [
        makeBranch('ready', '就绪', [
          makeStep('wait', 'A', 1),
          makeStep('click', 'B', 2)
        ]),
        makeBranch('pending', '等待', [makeStep('wait', 'C', 3)])
      ],
      [makeStep('wait', 'D', 4)]
    )
    const graph = projectStepDraftsToGraph([conditional])
    const displayState = createDefaultStepGraphDisplayState()
    displayState.nodeStates[createConditionalBranchPath(0, 'ready')] = {
      collapsed: true
    }
    const filtered = filterCollapsedStepGraph(graph, displayState)

    expect(getNode(filtered.nodes, createConditionalBranchPath(0, 'ready'))).toMatchObject({
      hiddenDescendantCount: 2
    })
    expect(
      filtered.nodes.map((node: StepGraphNode): string => node.path)
    ).toContain(createBranchChildPath(0, 'pending', 0))
    expect(
      filtered.nodes.map((node: StepGraphNode): string => node.path)
    ).not.toContain(createBranchChildPath(0, 'ready', 0))
  })

  it('collapses only the read-only component preview subtree', (): void => {
    const graph = projectStepDraftsToGraph(
      [makeStep('component_call', '登录组件', 1), makeStep('wait', '继续', 2)],
      { componentPreviews: { 42: makeComponentPreview() } }
    )
    const displayState = createDefaultStepGraphDisplayState()
    displayState.nodeStates[createTopStepPath(0)] = { collapsed: true }
    const filtered = filterCollapsedStepGraph(graph, displayState)

    expect(getNode(filtered.nodes, createTopStepPath(0))).toMatchObject({
      hiddenDescendantCount: 2
    })
    expect(
      filtered.nodes.some(
        (node: StepGraphNode): boolean => node.kind === 'component-preview'
      )
    ).toBe(false)
    expect(getNode(filtered.nodes, createTopStepPath(1)).label).toBe('继续')
  })
})

describe('immutable step graph operations', (): void => {
  it('inserts and reorders siblings with continuous numbers and path migration', (): void => {
    const original = deepFreeze([
      makeStep('wait', 'A', 1),
      makeStep('wait', 'B', 2),
      makeStep('wait', 'C', 3)
    ])
    const inserted = insertStepDraft(original, 'root', 1, makeStep('click', 'X', 4))

    expect(inserted.drafts.map((step: StepDraft): string => step.name)).toEqual([
      'A',
      'X',
      'B',
      'C'
    ])
    expect(inserted.drafts.map((step: StepDraft): number => step.stepNo)).toEqual([1, 2, 3, 4])
    expect(inserted.pathMigration['top:1']).toBe('top:2')

    const reordered = reorderStepDrafts(deepFreeze(inserted.drafts), 'root', 0, 3)
    expect(reordered.drafts.map((step: StepDraft): string => step.name)).toEqual([
      'X',
      'B',
      'C',
      'A'
    ])
    expect(reordered.pathMigration['top:0']).toBe('top:3')
    expect(original.map((step: StepDraft): string => step.name)).toEqual(['A', 'B', 'C'])

    const componentDrafts = deepFreeze([makeStep('component_call', '组件', 8)])
    const componentInserted = insertStepDraft(
      componentDrafts,
      'root',
      0,
      makeStep('wait', '前置', 9)
    )
    const componentDisplay = createDefaultStepGraphDisplayState()
    componentDisplay.nodeStates['top:0:component:child:0'] = { collapsed: true }
    const migratedComponentDisplay = migrateStepGraphDisplayState(
      componentDisplay,
      componentInserted.pathMigration
    )
    expect(migratedComponentDisplay.nodeStates).toEqual({
      'top:1:component:child:0': { collapsed: true }
    })
  })

  it('reorders branch siblings without changing their parent container', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [
        makeStep('wait', 'A', 1),
        makeStep('click', 'B', 2),
        makeStep('wait', 'C', 3)
      ])
    ])
    const branchPath = createConditionalBranchPath(0, 'ready')
    const reordered = reorderStepDrafts(deepFreeze([conditional]), branchPath, 2, 0)
    const branchSteps = reordered.drafts[0].conditionalBranches[0].steps

    expect(branchSteps.map((step: StepDraft): string => step.name)).toEqual(['C', 'A', 'B'])
    expect(branchSteps.map((step: StepDraft): number => step.stepNo)).toEqual([1, 2, 3])
    expect(reordered.pathMigration['top:0:branch:ready:child:2']).toBe(
      'top:0:branch:ready:child:0'
    )
  })

  it('moves an ordinary top step into a branch and migrates nested display state', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [makeStep('wait', '原子步骤', 3)])
    ])
    const original = deepFreeze([
      makeStep('click', '待移动', 1),
      conditional,
      makeStep('wait', '末尾', 2)
    ])
    const moved = moveStepDraft(
      original,
      createTopStepPath(0),
      createConditionalBranchPath(1, 'ready'),
      1
    )

    expect(moved.drafts.map((step: StepDraft): string => step.name)).toEqual(['条件', '末尾'])
    expect(moved.drafts[0].conditionalBranches[0].steps.map((step: StepDraft) => step.name)).toEqual([
      '原子步骤',
      '待移动'
    ])
    expect(moved.pathMigration['top:0']).toBe('top:0:branch:ready:child:1')
    expect(moved.pathMigration['top:1:branch:ready']).toBe('top:0:branch:ready')

    const displayState: StepGraphDisplayState = {
      nodeStates: {
        'top:0': { position: { x: 10, y: 20 }, color: '#123456' },
        'top:1:branch:ready': { collapsed: true },
        'top:2': { shape: 'rounded' }
      },
      annotations: [
        {
          id: 'relation',
          source: createTopStepPath(0),
          target: createTopStepPath(2),
          kind: 'dependency'
        }
      ],
      connectionStyle: 'step',
      background: { kind: 'solid', color: '#ffffff' }
    }
    const migrated = migrateStepGraphDisplayState(deepFreeze(displayState), moved.pathMigration)

    expect(migrated.nodeStates['top:0:branch:ready:child:1']).toEqual({
      position: { x: 10, y: 20 },
      color: '#123456'
    })
    expect(migrated.nodeStates['top:0:branch:ready']).toEqual({ collapsed: true })
    expect(migrated.annotations[0]).toMatchObject({
      source: 'top:0:branch:ready:child:1',
      target: 'top:1'
    })
  })

  it('deep-copies conditional subtrees and drops deleted display paths', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [
        makeStep('wait', '第一步', 1),
        makeStep('click', '第二步', 2)
      ])
    ])
    const original = deepFreeze([conditional])
    const duplicated = duplicateStepDraft(original, createTopStepPath(0))

    duplicated.drafts[1].conditionalBranches[0].steps[0].name = '副本已修改'
    expect(duplicated.drafts[0].conditionalBranches[0].steps[0].name).toBe('第一步')
    expect(original[0].conditionalBranches[0].steps[0].name).toBe('第一步')

    const deleted = deleteStepDraft(
      deepFreeze(duplicated.drafts),
      createBranchChildPath(0, 'ready', 0)
    )
    expect(deleted.drafts[0].conditionalBranches[0].steps[0]).toMatchObject({
      name: '第二步',
      stepNo: 1
    })
    expect(deleted.pathMigration['top:0:branch:ready:child:0']).toBeUndefined()
    expect(deleted.pathMigration['top:0:branch:ready:child:1']).toBe(
      'top:0:branch:ready:child:0'
    )

    const displayState = createDefaultStepGraphDisplayState()
    displayState.nodeStates['top:0:branch:ready:child:0'] = { color: '#ff0000' }
    const migrated = migrateStepGraphDisplayState(displayState, deleted.pathMigration)
    expect(migrated.nodeStates).toEqual({})
  })

  it('rejects illegal branch nesting, read-only paths, and emptying a branch', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [makeStep('wait', '唯一子步骤', 1)])
    ])
    const drafts = deepFreeze([conditional, makeStep('component_call', '组件', 2)])
    const branchPath = createConditionalBranchPath(0, 'ready')

    expectOperationError(
      (): unknown => insertStepDraft(drafts, branchPath, 1, makeStep('component_call', '非法', 3)),
      'INVALID_NESTING'
    )
    expectOperationError(
      (): unknown => moveStepDraft(drafts, createTopStepPath(1), branchPath, 1),
      'INVALID_NESTING'
    )
    expectOperationError(
      (): unknown => deleteStepDraft(drafts, createBranchChildPath(0, 'ready', 0)),
      'EMPTY_BRANCH'
    )
    expectOperationError(
      (): unknown =>
        deleteStepDraft(
          drafts,
          createComponentPreviewPath(1, 0) as unknown as EditableStepPath
        ),
      'READ_ONLY_PATH'
    )

    const emptyConditional = makeStep('conditional_branch', '空条件', 4)
    emptyConditional.conditionalBranches = []
    expectOperationError(
      (): unknown => insertStepDraft(drafts, 'root', 2, emptyConditional),
      'EMPTY_BRANCH'
    )
  })
})

describe('step graph drop constraints', (): void => {
  it('translates sibling insertion positions into a local reorder', (): void => {
    const drafts = deepFreeze([
      makeStep('wait', 'A', 1),
      makeStep('wait', 'B', 2),
      makeStep('wait', 'C', 3)
    ])
    const assessment = assessStepDraftDrop(
      drafts,
      createTopStepPath(0),
      'root',
      3
    )
    const result = moveStepDraftAtInsertion(
      drafts,
      createTopStepPath(0),
      'root',
      3
    )

    expect(assessment).toMatchObject({
      valid: true,
      operation: 'reorder',
      insertionIndex: 3
    })
    expect(result?.drafts.map((step: StepDraft): string => step.name)).toEqual([
      'B',
      'C',
      'A'
    ])
  })

  it('allows ordinary steps into branches and rejects unsupported nesting', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [makeStep('wait', '分支步骤', 1)])
    ])
    const drafts = deepFreeze([
      makeStep('click', '普通步骤', 2),
      makeStep('component_call', '组件', 3),
      conditional
    ])
    const targetPath = createConditionalBranchPath(2, 'ready')

    expect(
      assessStepDraftDrop(drafts, createTopStepPath(0), targetPath, 1)
    ).toMatchObject({
      valid: true,
      operation: 'move'
    })
    expect(
      assessStepDraftDrop(drafts, createTopStepPath(1), targetPath, 1)
    ).toMatchObject({
      valid: false,
      reason: '分支子步骤不支持 component_call 或 conditional_branch。'
    })
    expect(
      assessStepDraftDrop(drafts, createTopStepPath(2), targetPath, 1)
    ).toMatchObject({
      valid: false,
      reason: '分支子步骤不支持 component_call 或 conditional_branch。'
    })
  })

  it('rejects read-only preview drags and moves that empty a branch', (): void => {
    const conditional = makeConditionalStep('条件', [
      makeBranch('ready', '就绪', [makeStep('wait', '唯一步骤', 1)])
    ])
    const drafts = deepFreeze([
      conditional,
      makeStep('component_call', '组件', 2)
    ])

    expect(
      assessStepDraftDrop(
        drafts,
        createComponentPreviewPath(1, 0),
        'root',
        0
      )
    ).toMatchObject({
      valid: false,
      reason: '组件预览节点为只读，不能拖动。'
    })
    expect(
      assessStepDraftDrop(
        drafts,
        createBranchChildPath(0, 'ready', 0),
        'root',
        1
      )
    ).toMatchObject({
      valid: false,
      reason: '移动会清空条件分支，操作已拒绝。'
    })
  })
})

describe('payload and display-state isolation', (): void => {
  it('keeps display state out of StepWritePayload and does not mutate frozen drafts', (): void => {
    const child = createBranchChildStepDraft(0)
    child.name = '分支等待'
    const conditional = makeConditionalStep('条件', [makeBranch('ready', '就绪', [child])])
    const displayState = createDefaultStepGraphDisplayState()
    displayState.nodeStates['top:0'] = {
      position: { x: 320, y: 180 },
      collapsed: true,
      color: '#1677ff',
      shape: 'rounded',
      size: 'large'
    }
    displayState.annotations.push({
      id: 'display-only',
      source: createTopStepPath(0),
      target: createTopStepPath(1),
      kind: 'parallel'
    })
    const decorated = {
      ...makeStep('wait', '普通等待', 1),
      canvasDisplayState: displayState
    } as StepDraft & { canvasDisplayState: StepGraphDisplayState }
    const drafts = deepFreeze([conditional, decorated])

    const payload = buildStepGraphWritePayloads(drafts)
    const serialized = JSON.stringify(payload)

    expect(payload.map((item: StepWritePayload): number => item.stepNo)).toEqual([1, 2])
    expect(serialized).not.toContain('canvasDisplayState')
    expect(serialized).not.toContain('nodeStates')
    expect(serialized).not.toContain('display-only')

    const graph = projectStepDraftsToGraph(drafts)
    const displayedGraph = applyStepGraphDisplayState(deepFreeze(graph), displayState)
    expect(getNode(displayedGraph.nodes, 'top:0')).toMatchObject({
      position: { x: 320, y: 180 },
      width: 280,
      height: 120
    })
    expect(drafts[0].stepNo).toBe(1)
  })
})
