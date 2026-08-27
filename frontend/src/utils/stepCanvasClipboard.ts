import type {
  EditableStepPath,
  ParsedStepStructurePath,
  StepContainerPath,
  StepGraphMutationResult,
  StepGraphNode,
  StepPathMigration,
  StepStructurePath
} from '@/types/stepGraph'
import {
  createTopStepPath,
  deleteStepDraft,
  getStepContainerLength,
  getStepContainerPath,
  getStepDraftAtPath,
  insertStepDraft,
  isEditableStepPath,
  migrateStepStructurePath,
  parseStepStructurePath,
  projectStepDraftsToGraph,
  StepGraphOperationError
} from '@/utils/stepGraph'
import type { ConditionalBranchDraft, StepDraft } from '@/utils/steps'

export interface StepCanvasClipboardEntry {
  sourcePath: EditableStepPath
  step: StepDraft
}

export interface StepCanvasClipboard {
  entries: StepCanvasClipboardEntry[]
  source: 'copy' | 'cut'
}

export type StepCanvasTemporaryIdFactory = () => number
type ParsedEditableStepPath = Extract<
  ParsedStepStructurePath,
  { kind: 'top-step' | 'branch-child' | 'else-child' }
>

let nextTemporaryId = -Date.now()

export function createStepCanvasTemporaryId(): number {
  nextTemporaryId = Math.min(nextTemporaryId - 1, -Date.now() - 1)
  return nextTemporaryId
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

export function regenerateStepDraftTemporaryIds(
  source: StepDraft,
  createId: StepCanvasTemporaryIdFactory = createStepCanvasTemporaryId
): StepDraft {
  const step = cloneValue(source)

  function regenerate(current: StepDraft): void {
    current.id = createId()
    current.conditionalBranches.forEach((branch: ConditionalBranchDraft): void => {
      branch.id = createId()
      branch.steps.forEach(regenerate)
    })
    current.elseSteps.forEach(regenerate)
  }

  regenerate(step)
  return step
}

function compareEditablePaths(
  left: EditableStepPath,
  right: EditableStepPath
): number {
  const leftPath = parseEditableStepPath(left)
  const rightPath = parseEditableStepPath(right)

  const leftTopIndex = leftPath.topIndex
  const rightTopIndex = rightPath.topIndex
  if (leftTopIndex !== rightTopIndex) {
    return leftTopIndex - rightTopIndex
  }

  const kindOrder = {
    'top-step': 0,
    'branch-child': 1,
    'else-child': 2
  } as const
  const kindDifference =
    kindOrder[leftPath.kind as keyof typeof kindOrder] -
    kindOrder[rightPath.kind as keyof typeof kindOrder]
  if (kindDifference !== 0) {
    return kindDifference
  }

  if (leftPath.kind === 'branch-child' && rightPath.kind === 'branch-child') {
    const branchDifference = leftPath.branchKey.localeCompare(rightPath.branchKey)
    return branchDifference || leftPath.childIndex - rightPath.childIndex
  }
  if (leftPath.kind === 'else-child' && rightPath.kind === 'else-child') {
    return leftPath.childIndex - rightPath.childIndex
  }
  return 0
}

function parseEditableStepPath(path: EditableStepPath): ParsedEditableStepPath {
  const parsed = parseStepStructurePath(path)
  if (
    parsed?.kind === 'top-step' ||
    parsed?.kind === 'branch-child' ||
    parsed?.kind === 'else-child'
  ) {
    return parsed
  }
  throw new StepGraphOperationError('INVALID_PATH', `无效的可编辑步骤路径：${path}`)
}

function normalizeSelection(paths: readonly StepStructurePath[]): EditableStepPath[] {
  const editablePaths = [...new Set(paths.filter(isEditableStepPath))]
  const selectedTopIndexes = new Set(
    editablePaths.flatMap((path: EditableStepPath): number[] => {
      const parsed = parseStepStructurePath(path)
      return parsed?.kind === 'top-step' ? [parsed.topIndex] : []
    })
  )

  return editablePaths
    .filter((path: EditableStepPath): boolean => {
      const parsed = parseEditableStepPath(path)
      return (
        parsed.kind === 'top-step' ||
        !selectedTopIndexes.has(parsed.topIndex)
      )
    })
    .sort(compareEditablePaths)
}

export function copyStepDraftSelection(
  drafts: readonly StepDraft[],
  paths: readonly StepStructurePath[],
  source: StepCanvasClipboard['source'] = 'copy'
): StepCanvasClipboard {
  const entries = normalizeSelection(paths).map(
    (path: EditableStepPath): StepCanvasClipboardEntry => ({
      sourcePath: path,
      step: cloneValue(getStepDraftAtPath(drafts, path))
    })
  )
  if (entries.length === 0) {
    throw new StepGraphOperationError('INVALID_PATH', '请先选择可编辑步骤。')
  }
  return { entries, source }
}

function composePathMigrations(
  first: StepPathMigration,
  second: StepPathMigration
): StepPathMigration {
  const result: Record<string, StepStructurePath> = {}
  for (const [originalPath, intermediatePath] of Object.entries(first)) {
    const finalPath = migrateStepStructurePath(intermediatePath, second)
    if (finalPath) {
      result[originalPath] = finalPath
    }
  }
  return result
}

export function pasteStepDraftClipboard(
  drafts: readonly StepDraft[],
  clipboard: StepCanvasClipboard,
  targetContainerPath: StepContainerPath,
  targetIndex: number,
  createId: StepCanvasTemporaryIdFactory = createStepCanvasTemporaryId
): StepGraphMutationResult<StepDraft> {
  if (clipboard.entries.length === 0) {
    throw new StepGraphOperationError('INVALID_PATH', '剪贴板中没有可粘贴的步骤。')
  }

  let nextDrafts = cloneValue(Array.from(drafts))
  let pathMigration: StepPathMigration | null = null
  let focusPath: EditableStepPath | null = null

  clipboard.entries.forEach(
    (entry: StepCanvasClipboardEntry, offset: number): void => {
      const result = insertStepDraft(
        nextDrafts,
        targetContainerPath,
        targetIndex + offset,
        regenerateStepDraftTemporaryIds(entry.step, createId)
      )
      pathMigration = pathMigration
        ? composePathMigrations(pathMigration, result.pathMigration)
        : result.pathMigration
      nextDrafts = result.drafts
      focusPath = result.focusPath
    }
  )

  return {
    drafts: nextDrafts,
    pathMigration: pathMigration ?? { root: 'root' },
    focusPath
  }
}

function getDeletionOrder(paths: readonly EditableStepPath[]): EditableStepPath[] {
  return [...paths].sort(
    (left: EditableStepPath, right: EditableStepPath): number => {
      const leftPath = parseStepStructurePath(left)
      const rightPath = parseStepStructurePath(right)
      if (!leftPath || !rightPath) {
        return right.localeCompare(left)
      }

      const leftIsTop = leftPath.kind === 'top-step'
      const rightIsTop = rightPath.kind === 'top-step'
      if (leftIsTop !== rightIsTop) {
        return leftIsTop ? 1 : -1
      }
      return -compareEditablePaths(left, right)
    }
  )
}

export function deleteStepDraftSelection(
  drafts: readonly StepDraft[],
  paths: readonly StepStructurePath[]
): StepGraphMutationResult<StepDraft> {
  const normalizedPaths = normalizeSelection(paths)
  if (normalizedPaths.length === 0) {
    throw new StepGraphOperationError('INVALID_PATH', '请先选择可编辑步骤。')
  }

  const selectedByContainer = new Map<StepContainerPath, number>()
  normalizedPaths.forEach((path: EditableStepPath): void => {
    const containerPath = getStepContainerPath(path)
    selectedByContainer.set(
      containerPath,
      (selectedByContainer.get(containerPath) ?? 0) + 1
    )
  })
  selectedByContainer.forEach(
    (selectedCount: number, containerPath: StepContainerPath): void => {
      if (
        containerPath !== 'root' &&
        selectedCount >= getStepContainerLength(drafts, containerPath)
      ) {
        throw new StepGraphOperationError(
          'EMPTY_BRANCH',
          '条件分支必须至少保留一个子步骤。'
        )
      }
    }
  )

  let nextDrafts = cloneValue(Array.from(drafts))
  let pathMigration: StepPathMigration | null = null
  let focusPath: EditableStepPath | null = null
  for (const path of getDeletionOrder(normalizedPaths)) {
    const result = deleteStepDraft(nextDrafts, path)
    pathMigration = pathMigration
      ? composePathMigrations(pathMigration, result.pathMigration)
      : result.pathMigration
    nextDrafts = result.drafts
    focusPath = result.focusPath
  }

  if (
    focusPath &&
    !projectStepDraftsToGraph(nextDrafts).nodes.some(
      (node: StepGraphNode): boolean => node.path === focusPath
    )
  ) {
    const firstEditablePath = projectStepDraftsToGraph(nextDrafts).nodes.find(
      (node: StepGraphNode): boolean => isEditableStepPath(node.path)
    )?.path
    focusPath = firstEditablePath && isEditableStepPath(firstEditablePath)
      ? firstEditablePath
      : null
  }

  return {
    drafts: nextDrafts,
    pathMigration: pathMigration ?? {
      root: 'root',
      ...Object.fromEntries(
        drafts.map((_step: StepDraft, index: number): [string, EditableStepPath] => [
          createTopStepPath(index),
          createTopStepPath(index)
        ])
      )
    },
    focusPath
  }
}
