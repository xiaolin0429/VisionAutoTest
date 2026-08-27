import { describe, expect, it, vi } from 'vitest'

import type {
  StepGraph,
  StepGraphDisplayState,
  StepGraphMutationResult,
  StepGraphNode
} from '@/types/stepGraph'
import {
  createConditionalBranchPath,
  createDefaultStepGraphDisplayState,
  deleteStepDraft,
  insertStepDraft,
  layoutStepGraph,
  migrateStepGraphDisplayState,
  moveStepDraft,
  reorderStepDrafts
} from '@/utils/stepGraph'
import {
  createStepGraphIncrementalPipeline,
  projectStepDraftTopLevelSubgraph
} from '@/utils/stepGraphIncremental'
import {
  createBranchChildStepDraft,
  createEmptyStepDraft,
  normalizeStepByType,
  type ConditionalBranchDraft,
  type StepDraft
} from '@/utils/steps'

function createDrafts(): StepDraft[] {
  const before = createEmptyStepDraft(0)
  before.id = 1
  before.name = '前置等待'

  const conditional = createEmptyStepDraft(1)
  conditional.id = 2
  conditional.name = '环境分支'
  Object.assign(
    conditional,
    normalizeStepByType(conditional, 'conditional_branch')
  )
  conditional.conditionalBranches[0].id = 20
  conditional.conditionalBranches[0].branchKey = 'desktop'
  conditional.conditionalBranches[0].branchName = '桌面端'
  conditional.conditionalBranches[0].ocrTarget.text = 'desktop'
  conditional.conditionalBranches[0].steps[0].id = 21
  const mobileStep = createBranchChildStepDraft(0)
  mobileStep.id = 31
  mobileStep.name = '移动端等待'
  const mobileBranch: ConditionalBranchDraft = {
    ...conditional.conditionalBranches[0],
    id: 30,
    branchKey: 'mobile',
    branchName: '移动端',
    ocrTarget: {
      ...conditional.conditionalBranches[0].ocrTarget,
      text: 'mobile'
    },
    steps: [mobileStep]
  }
  conditional.conditionalBranches.push(mobileBranch)

  const after = createEmptyStepDraft(2)
  after.id = 3
  after.name = '结束等待'
  return [before, conditional, after]
}

function getNode(graph: StepGraph, path: string): StepGraphNode {
  const node = graph.nodes.find(
    (candidate: StepGraphNode): boolean => candidate.path === path
  )
  if (!node) {
    throw new Error(`Missing node ${path}`)
  }
  return node
}

describe('incremental step graph pipeline', (): void => {
  it('projects and lays out only the affected top subtree for branch structure commands', (): void => {
    const projectTopLevel = vi.fn(projectStepDraftTopLevelSubgraph)
    const layoutTopLevel = vi.fn(
      (graph: StepGraph, _topIndex: number): StepGraph =>
        layoutStepGraph(graph)
    )
    const pipeline = createStepGraphIncrementalPipeline({
      projectTopLevel,
      layoutTopLevel
    })
    const displayState = createDefaultStepGraphDisplayState()
    let drafts = createDrafts()
    let current = pipeline.initialize(drafts, {}, displayState)
    const beforeProjected = getNode(current.projectedGraph, 'top:0')
    const afterProjected = getNode(current.projectedGraph, 'top:2')
    const beforeCanvas = getNode(current.canvasGraph, 'top:0')
    const afterCanvas = getNode(current.canvasGraph, 'top:2')
    const beforePosition = beforeCanvas.position
    const afterPosition = afterCanvas.position

    function applyMutation(
      mutation: StepGraphMutationResult<StepDraft>
    ): void {
      projectTopLevel.mockClear()
      layoutTopLevel.mockClear()
      drafts = mutation.drafts
      current = pipeline.updateStructure(
        drafts,
        mutation.pathMigration,
        {},
        displayState
      )
      expect(current.projectedTopPaths).toEqual(['top:1'])
      expect(current.laidOutTopPaths).toEqual(['top:1'])
      expect(projectTopLevel).toHaveBeenCalledTimes(1)
      expect(layoutTopLevel).toHaveBeenCalledTimes(1)
      expect(projectTopLevel.mock.calls[0]?.[1]).toBe(1)
      expect(getNode(current.projectedGraph, 'top:0')).toBe(beforeProjected)
      expect(getNode(current.projectedGraph, 'top:2')).toBe(afterProjected)
      expect(getNode(current.canvasGraph, 'top:0')).toBe(beforeCanvas)
      expect(getNode(current.canvasGraph, 'top:2')).toBe(afterCanvas)
      expect(beforeCanvas.position).toBe(beforePosition)
      expect(afterCanvas.position).toBe(afterPosition)
    }

    const desktopPath = createConditionalBranchPath(1, 'desktop')
    const mobilePath = createConditionalBranchPath(1, 'mobile')
    const inserted = createBranchChildStepDraft(1)
    inserted.id = 22
    inserted.name = '桌面端点击'
    Object.assign(inserted, normalizeStepByType(inserted, 'click'))
    inserted.selector = '#desktop'
    applyMutation(insertStepDraft(drafts, desktopPath, 1, inserted))
    applyMutation(reorderStepDrafts(drafts, desktopPath, 1, 0))
    applyMutation(
      moveStepDraft(
        drafts,
        'top:1:branch:desktop:child:0',
        mobilePath,
        1
      )
    )
    applyMutation(deleteStepDraft(drafts, 'top:1:branch:mobile:child:1'))
  })

  it('reuses all top subgraphs for root reorder and keeps collapsed descendants hidden', (): void => {
    const projectTopLevel = vi.fn(projectStepDraftTopLevelSubgraph)
    const layoutTopLevel = vi.fn(
      (graph: StepGraph, _topIndex: number): StepGraph =>
        layoutStepGraph(graph)
    )
    const pipeline = createStepGraphIncrementalPipeline({
      projectTopLevel,
      layoutTopLevel
    })
    const displayState: StepGraphDisplayState =
      createDefaultStepGraphDisplayState()
    displayState.nodeStates['top:1'] = { collapsed: true }
    const drafts = createDrafts()
    const initial = pipeline.initialize(drafts, {}, displayState)
    const originalNodes = initial.projectedGraph.nodes.filter(
      (node: StepGraphNode): boolean => node.kind === 'top-step'
    )
    const mutation = reorderStepDrafts(drafts, 'root', 2, 0)
    const migratedDisplayState = migrateStepGraphDisplayState(
      displayState,
      mutation.pathMigration
    )

    projectTopLevel.mockClear()
    layoutTopLevel.mockClear()
    const updated = pipeline.updateStructure(
      mutation.drafts,
      mutation.pathMigration,
      {},
      migratedDisplayState
    )

    expect(updated.projectedTopPaths).toEqual([])
    expect(updated.laidOutTopPaths).toEqual([])
    expect(projectTopLevel).not.toHaveBeenCalled()
    expect(layoutTopLevel).not.toHaveBeenCalled()
    expect(
      updated.projectedGraph.nodes.filter(
        (node: StepGraphNode): boolean => node.kind === 'top-step'
      )
    ).toEqual(expect.arrayContaining(originalNodes))
    expect(
      updated.canvasGraph.nodes.some(
        (node: StepGraphNode): boolean =>
          node.path.startsWith('top:2:branch:')
      )
    ).toBe(false)
    expect(getNode(updated.canvasGraph, 'top:2').hiddenDescendantCount).toBe(4)
    expect(getNode(updated.canvasGraph, 'top:0').position.y).toBeLessThan(
      getNode(updated.canvasGraph, 'top:1').position.y
    )
    expect(getNode(updated.canvasGraph, 'top:1').position.y).toBeLessThan(
      getNode(updated.canvasGraph, 'top:2').position.y
    )
  })
})
