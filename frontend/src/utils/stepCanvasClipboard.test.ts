import { describe, expect, it } from 'vitest'

import {
  copyStepDraftSelection,
  pasteStepDraftClipboard,
  regenerateStepDraftTemporaryIds
} from '@/utils/stepCanvasClipboard'
import {
  createBranchChildPath,
  createTopStepPath
} from '@/utils/stepGraph'
import {
  createEmptyStepDraft,
  type StepDraft
} from '@/utils/steps'

function createConditionalDraft(): StepDraft {
  const draft = createEmptyStepDraft(0)
  draft.id = 10
  draft.type = 'conditional_branch'
  draft.templateId = 81
  draft.componentId = 91
  draft.conditionalBranches[0].id = 11
  draft.conditionalBranches[0].branchKey = 'ready'
  draft.conditionalBranches[0].steps[0].id = 12
  draft.conditionalBranches[0].steps[0].templateId = 82
  draft.elseSteps[0].id = 13
  draft.elseSteps[0].componentId = 92
  return draft
}

function collectDraftIds(step: StepDraft): number[] {
  return [
    step.id,
    ...step.conditionalBranches.flatMap((branch) => [
      branch.id,
      ...branch.steps.flatMap(collectDraftIds)
    ]),
    ...step.elseSteps.flatMap(collectDraftIds)
  ]
}

describe('step canvas clipboard', (): void => {
  it('regenerates every nested temporary id while preserving resource references', (): void => {
    const source = createConditionalDraft()
    let nextId = -100
    const pasted = regenerateStepDraftTemporaryIds(
      source,
      (): number => nextId--
    )

    const sourceIds = new Set(collectDraftIds(source))
    const pastedIds = collectDraftIds(pasted)
    expect(new Set(pastedIds).size).toBe(pastedIds.length)
    expect(pastedIds.every((id: number): boolean => !sourceIds.has(id))).toBe(true)
    expect(pasted.templateId).toBe(81)
    expect(pasted.componentId).toBe(91)
    expect(pasted.conditionalBranches[0].steps[0].templateId).toBe(82)
    expect(pasted.elseSteps[0].componentId).toBe(92)
    expect(source.id).toBe(10)
  })

  it('deep-copies multiple selections and omits descendants of a copied subtree', (): void => {
    const conditional = createConditionalDraft()
    const trailing = createEmptyStepDraft(1)
    trailing.id = 20
    trailing.name = '尾部步骤'
    const drafts = [conditional, trailing]
    const clipboard = copyStepDraftSelection(drafts, [
      createTopStepPath(0),
      createBranchChildPath(0, 'ready', 0),
      createTopStepPath(1)
    ])
    let nextId = -200
    const result = pasteStepDraftClipboard(
      drafts,
      clipboard,
      'root',
      2,
      (): number => nextId--
    )

    expect(clipboard.entries).toHaveLength(2)
    expect(result.drafts).toHaveLength(4)
    expect(result.drafts[2].conditionalBranches[0].steps).toHaveLength(1)
    expect(result.drafts[3].name).toBe('尾部步骤')
    result.drafts[2].conditionalBranches[0].steps[0].name = '仅修改副本'
    expect(drafts[0].conditionalBranches[0].steps[0].name).not.toBe('仅修改副本')
  })
})
