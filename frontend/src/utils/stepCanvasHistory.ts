export interface StepCanvasHistoryOptions<T> {
  limit?: number
  clone?: (value: T) => T
  equals?: (left: T, right: T) => boolean
}

export interface StepCanvasHistoryCommitOptions {
  mergeKey?: string | null
}

export interface StepCanvasHistory<T> {
  readonly current: T
  readonly canUndo: boolean
  readonly canRedo: boolean
  readonly undoCount: number
  commit: (nextValue: T, options?: StepCanvasHistoryCommitOptions) => boolean
  undo: () => T | null
  redo: () => T | null
  endMerge: (mergeKey?: string) => void
  reset: (value: T) => void
}

const DEFAULT_HISTORY_LIMIT = 50

function cloneValue<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item: unknown): unknown => cloneValue(item)) as T
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(
        ([key, item]: [string, unknown]): [string, unknown] => [
          key,
          cloneValue(item)
        ]
      )
    ) as T
  }
  return value
}

function valuesEqual<T>(left: T, right: T): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

export function createStepCanvasHistory<T>(
  initialValue: T,
  options: StepCanvasHistoryOptions<T> = {}
): StepCanvasHistory<T> {
  const limit = Math.max(1, Math.floor(options.limit ?? DEFAULT_HISTORY_LIMIT))
  const clone = options.clone ?? cloneValue
  const equals = options.equals ?? valuesEqual
  const undoStack: T[] = []
  const redoStack: T[] = []
  let currentValue = clone(initialValue)
  let activeMergeKey: string | null = null

  function commit(
    nextValue: T,
    commitOptions: StepCanvasHistoryCommitOptions = {}
  ): boolean {
    if (equals(currentValue, nextValue)) {
      return false
    }

    const mergeKey = commitOptions.mergeKey?.trim() || null
    if (!mergeKey || mergeKey !== activeMergeKey) {
      undoStack.push(clone(currentValue))
      if (undoStack.length > limit) {
        undoStack.splice(0, undoStack.length - limit)
      }
    }

    currentValue = clone(nextValue)
    redoStack.splice(0)
    activeMergeKey = mergeKey
    return true
  }

  function undo(): T | null {
    const previous = undoStack.pop()
    if (!previous) {
      return null
    }
    redoStack.push(clone(currentValue))
    currentValue = clone(previous)
    activeMergeKey = null
    return clone(currentValue)
  }

  function redo(): T | null {
    const next = redoStack.pop()
    if (!next) {
      return null
    }
    undoStack.push(clone(currentValue))
    currentValue = clone(next)
    activeMergeKey = null
    return clone(currentValue)
  }

  function endMerge(mergeKey?: string): void {
    if (mergeKey === undefined || activeMergeKey === mergeKey) {
      activeMergeKey = null
    }
  }

  function reset(value: T): void {
    undoStack.splice(0)
    redoStack.splice(0)
    currentValue = clone(value)
    activeMergeKey = null
  }

  return {
    get current(): T {
      return clone(currentValue)
    },
    get canUndo(): boolean {
      return undoStack.length > 0
    },
    get canRedo(): boolean {
      return redoStack.length > 0
    },
    get undoCount(): number {
      return undoStack.length
    },
    commit,
    undo,
    redo,
    endMerge,
    reset
  }
}
