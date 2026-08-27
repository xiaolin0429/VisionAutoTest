import { effectScope, nextTick, ref, type EffectScope } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import {
  useStepCanvasEditor,
  type UseStepCanvasEditorResult
} from '@/composables/useStepCanvasEditor'
import {
  createDefaultStepGraphDisplayState,
  createTopStepPath
} from '@/utils/stepGraph'
import { createEmptyStepDraft } from '@/utils/steps'

const scopes: EffectScope[] = []

afterEach((): void => {
  scopes.splice(0).forEach((scope: EffectScope): void => scope.stop())
})

function createEditorHarness(): {
  editor: UseStepCanvasEditorResult
  dirtyChanges: boolean[]
} {
  const scope = effectScope()
  scopes.push(scope)
  const dirtyChanges: boolean[] = []
  let editor: UseStepCanvasEditorResult | null = null
  scope.run((): void => {
    const displayState = ref(createDefaultStepGraphDisplayState())
    editor = useStepCanvasEditor({
      displayState,
      replaceDisplayState(state): void {
        displayState.value = state
      },
      onDirtyChange(value: boolean): void {
        dirtyChanges.push(value)
      }
    })
  })
  if (!editor) {
    throw new Error('Editor harness failed to initialize.')
  }
  return { editor, dirtyChanges }
}

describe('useStepCanvasEditor', (): void => {
  it('keeps display-only history undoable without marking business drafts dirty', (): void => {
    const { editor, dirtyChanges } = createEditorHarness()
    editor.initialize([createEmptyStepDraft(0)])
    const display = createDefaultStepGraphDisplayState()
    display.nodeStates[createTopStepPath(0)] = {
      color: '#2563eb',
      shape: 'rounded',
      size: 'large'
    }
    display.annotations.push({
      id: 'dependency-1',
      source: createTopStepPath(0),
      target: createTopStepPath(1),
      kind: 'dependency'
    })

    editor.commitDisplayState(display)

    expect(editor.dirty.value).toBe(false)
    expect(editor.canUndo.value).toBe(true)
    expect(editor.undo()).toBe(true)
    expect(editor.dirty.value).toBe(false)
    expect(dirtyChanges).not.toContain(true)
  })

  it('merges changes made during one input focus session', async (): Promise<void> => {
    const { editor } = createEditorHarness()
    const draft = createEmptyStepDraft(0)
    draft.name = '原名称'
    editor.initialize([draft])

    editor.beginInputSession('top:0:name')
    editor.stepDrafts.value[0].name = '新'
    await nextTick()
    editor.stepDrafts.value[0].name = '新名称'
    await nextTick()
    editor.endInputSession('top:0:name')

    expect(editor.historySize.value).toBe(1)
    expect(editor.dirty.value).toBe(true)
    expect(editor.undo()).toBe(true)
    expect(editor.stepDrafts.value[0].name).toBe('原名称')
    expect(editor.dirty.value).toBe(false)
  })
})
