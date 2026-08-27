import {
  computed,
  ref,
  watch,
  type ComputedRef,
  type Ref
} from 'vue'

import type { StepGraphDisplayState } from '@/types/stepGraph'
import { createStepCanvasHistory } from '@/utils/stepCanvasHistory'
import type { StepDraft } from '@/utils/steps'

export interface StepCanvasEditorSnapshot {
  drafts: StepDraft[]
  displayState: StepGraphDisplayState
}

export interface UseStepCanvasEditorOptions {
  displayState: Ref<StepGraphDisplayState>
  replaceDisplayState: (state: StepGraphDisplayState) => void
  onDraftsChange?: (drafts: StepDraft[]) => void
  onDirtyChange?: (dirty: boolean) => void
}

export interface UseStepCanvasEditorResult {
  stepDrafts: Ref<StepDraft[]>
  dirty: Ref<boolean>
  canUndo: ComputedRef<boolean>
  canRedo: ComputedRef<boolean>
  historySize: ComputedRef<number>
  initialize: (drafts: readonly StepDraft[]) => void
  markSaved: (drafts?: readonly StepDraft[]) => void
  commitDrafts: (drafts: readonly StepDraft[]) => void
  commitDisplayState: (state: StepGraphDisplayState) => void
  commitSnapshot: (
    drafts: readonly StepDraft[],
    state: StepGraphDisplayState,
    mergeInputSession?: boolean
  ) => void
  beginInputSession: (key: string) => void
  endInputSession: (key?: string) => void
  undo: () => boolean
  redo: () => boolean
}

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

function serializeDrafts(drafts: readonly StepDraft[]): string {
  return JSON.stringify(drafts)
}

function cloneDrafts(drafts: readonly StepDraft[]): StepDraft[] {
  return cloneValue(Array.from(drafts))
}

export function useStepCanvasEditor(
  options: UseStepCanvasEditorOptions
): UseStepCanvasEditorResult {
  const stepDrafts = ref<StepDraft[]>([])
  const dirty = ref(false)
  const historyVersion = ref(0)
  const initialized = ref(false)
  const history = createStepCanvasHistory<StepCanvasEditorSnapshot>(
    {
      drafts: [],
      displayState: cloneValue(options.displayState.value)
    },
    { limit: 50 }
  )
  let baselineDrafts = '[]'
  let applyingSnapshot = false
  let activeInputSession: string | null = null

  const canUndo = computed((): boolean => {
    void historyVersion.value
    return history.canUndo
  })
  const canRedo = computed((): boolean => {
    void historyVersion.value
    return history.canRedo
  })
  const historySize = computed((): number => {
    void historyVersion.value
    return history.undoCount
  })

  function createSnapshot(
    drafts: readonly StepDraft[] = stepDrafts.value,
    displayState: StepGraphDisplayState = options.displayState.value
  ): StepCanvasEditorSnapshot {
    return {
      drafts: cloneDrafts(drafts),
      displayState: cloneValue(displayState)
    }
  }

  function updateDirtyState(): void {
    const nextDirty = serializeDrafts(stepDrafts.value) !== baselineDrafts
    if (dirty.value === nextDirty) {
      return
    }
    dirty.value = nextDirty
    options.onDirtyChange?.(nextDirty)
  }

  function notifyDraftsChange(): void {
    options.onDraftsChange?.(cloneValue(stepDrafts.value))
    updateDirtyState()
  }

  function assignSnapshot(snapshot: StepCanvasEditorSnapshot): void {
    applyingSnapshot = true
    try {
      stepDrafts.value = cloneValue(snapshot.drafts)
      options.replaceDisplayState(cloneValue(snapshot.displayState))
    } finally {
      applyingSnapshot = false
    }
    historyVersion.value += 1
    notifyDraftsChange()
  }

  function initialize(drafts: readonly StepDraft[]): void {
    applyingSnapshot = true
    try {
      stepDrafts.value = cloneDrafts(drafts)
    } finally {
      applyingSnapshot = false
    }
    baselineDrafts = serializeDrafts(stepDrafts.value)
    history.reset(createSnapshot())
    historyVersion.value += 1
    activeInputSession = null
    initialized.value = true
    if (dirty.value) {
      dirty.value = false
      options.onDirtyChange?.(false)
    }
  }

  function markSaved(drafts: readonly StepDraft[] = stepDrafts.value): void {
    applyingSnapshot = true
    try {
      stepDrafts.value = cloneDrafts(drafts)
    } finally {
      applyingSnapshot = false
    }
    baselineDrafts = serializeDrafts(stepDrafts.value)
    history.reset(createSnapshot())
    historyVersion.value += 1
    activeInputSession = null
    if (dirty.value) {
      dirty.value = false
      options.onDirtyChange?.(false)
    }
  }

  function commitDrafts(drafts: readonly StepDraft[]): void {
    activeInputSession = null
    const snapshot = createSnapshot(drafts)
    if (!history.commit(snapshot)) {
      return
    }
    applyingSnapshot = true
    try {
      stepDrafts.value = cloneDrafts(drafts)
    } finally {
      applyingSnapshot = false
    }
    historyVersion.value += 1
    notifyDraftsChange()
  }

  function commitDisplayState(state: StepGraphDisplayState): void {
    activeInputSession = null
    const snapshot = createSnapshot(stepDrafts.value, state)
    if (!history.commit(snapshot)) {
      return
    }
    applyingSnapshot = true
    try {
      options.replaceDisplayState(cloneValue(state))
    } finally {
      applyingSnapshot = false
    }
    historyVersion.value += 1
  }

  function commitSnapshot(
    drafts: readonly StepDraft[],
    state: StepGraphDisplayState,
    mergeInputSession = false
  ): void {
    const mergeKey = mergeInputSession ? activeInputSession : null
    if (!mergeInputSession) {
      activeInputSession = null
    }
    const snapshot = createSnapshot(drafts, state)
    if (!history.commit(snapshot, { mergeKey })) {
      return
    }
    applyingSnapshot = true
    try {
      stepDrafts.value = cloneDrafts(drafts)
      options.replaceDisplayState(cloneValue(state))
    } finally {
      applyingSnapshot = false
    }
    historyVersion.value += 1
    notifyDraftsChange()
  }

  function beginInputSession(key: string): void {
    const normalizedKey = key.trim()
    if (!normalizedKey) {
      return
    }
    if (activeInputSession && activeInputSession !== normalizedKey) {
      history.endMerge(activeInputSession)
    }
    activeInputSession = normalizedKey
  }

  function endInputSession(key?: string): void {
    if (key && activeInputSession !== key) {
      return
    }
    history.endMerge(activeInputSession ?? undefined)
    activeInputSession = null
  }

  function undo(): boolean {
    endInputSession()
    const snapshot = history.undo()
    if (!snapshot) {
      return false
    }
    assignSnapshot(snapshot)
    return true
  }

  function redo(): boolean {
    endInputSession()
    const snapshot = history.redo()
    if (!snapshot) {
      return false
    }
    assignSnapshot(snapshot)
    return true
  }

  watch(
    stepDrafts,
    (drafts: StepDraft[]): void => {
      if (!initialized.value || applyingSnapshot) {
        return
      }
      const committed = history.commit(createSnapshot(drafts), {
        mergeKey: activeInputSession
      })
      if (!committed) {
        return
      }
      historyVersion.value += 1
      notifyDraftsChange()
    },
    { deep: true }
  )

  watch(
    options.displayState,
    (state: StepGraphDisplayState): void => {
      if (!initialized.value || applyingSnapshot) {
        return
      }
      if (!history.commit(createSnapshot(stepDrafts.value, state))) {
        return
      }
      historyVersion.value += 1
    },
    { deep: true }
  )

  return {
    stepDrafts,
    dirty,
    canUndo,
    canRedo,
    historySize,
    initialize,
    markSaved,
    commitDrafts,
    commitDisplayState,
    commitSnapshot,
    beginInputSession,
    endInputSession,
    undo,
    redo
  }
}
