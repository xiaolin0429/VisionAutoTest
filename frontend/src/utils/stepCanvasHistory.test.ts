import { describe, expect, it } from 'vitest'

import { createStepCanvasHistory } from '@/utils/stepCanvasHistory'

interface HistoryState {
  value: number
  label: string
}

describe('step canvas command history', (): void => {
  it('keeps at most 50 undo snapshots', (): void => {
    const history = createStepCanvasHistory<HistoryState>({
      value: 0,
      label: 'initial'
    })

    for (let value = 1; value <= 60; value += 1) {
      history.commit({ value, label: `value-${value}` })
    }

    expect(history.undoCount).toBe(50)
    for (let index = 0; index < 50; index += 1) {
      history.undo()
    }
    expect(history.current.value).toBe(10)
    expect(history.canUndo).toBe(false)
  })

  it('merges one focused input session and preserves redo semantics', (): void => {
    const history = createStepCanvasHistory<HistoryState>({
      value: 1,
      label: 'A'
    })

    history.commit({ value: 1, label: 'AB' }, { mergeKey: 'name-field' })
    history.commit({ value: 1, label: 'ABC' }, { mergeKey: 'name-field' })
    history.endMerge('name-field')
    history.commit({ value: 2, label: 'ABC' })

    expect(history.undoCount).toBe(2)
    expect(history.undo()).toEqual({ value: 1, label: 'ABC' })
    expect(history.undo()).toEqual({ value: 1, label: 'A' })
    expect(history.redo()).toEqual({ value: 1, label: 'ABC' })

    history.commit({ value: 3, label: 'new branch' })
    expect(history.canRedo).toBe(false)
  })
})
