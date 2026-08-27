import type { StepType } from '@/types/models'

export type StepGraphRootPath = 'root'
export type TopStepPath = `top:${number}`
export type ConditionalBranchPath = `${TopStepPath}:branch:${string}`
export type ElseBranchPath = `${TopStepPath}:else`
export type BranchChildPath = `${ConditionalBranchPath}:child:${number}`
export type ElseChildPath = `${ElseBranchPath}:child:${number}`
export type ComponentPreviewPath = `${TopStepPath}:component:child:${number}`

export type StepContainerPath =
  | StepGraphRootPath
  | ConditionalBranchPath
  | ElseBranchPath

export type EditableStepPath = TopStepPath | BranchChildPath | ElseChildPath

export type StepStructurePath =
  | StepContainerPath
  | EditableStepPath
  | ComponentPreviewPath

export type ParsedStepStructurePath =
  | { kind: 'root' }
  | { kind: 'top-step'; topIndex: number }
  | { kind: 'branch'; topIndex: number; branchKey: string }
  | { kind: 'branch-child'; topIndex: number; branchKey: string; childIndex: number }
  | { kind: 'else'; topIndex: number }
  | { kind: 'else-child'; topIndex: number; childIndex: number }
  | { kind: 'component-preview'; topIndex: number; childIndex: number }

export type StepGraphNodeKind =
  | 'root'
  | 'top-step'
  | 'branch-lane'
  | 'else-lane'
  | 'branch-step'
  | 'component-preview'

export type StepGraphEdgeKind =
  | 'sequence'
  | 'condition'
  | 'else'
  | 'component'
  | 'dependency-annotation'
  | 'parallel-annotation'

export type StepGraphAnnotationKind = 'dependency' | 'parallel'
export type StepGraphConnectionStyle = 'straight' | 'step' | 'bezier'
export type StepGraphNodeShape = 'rectangle' | 'rounded'
export type StepGraphNodeSize = 'small' | 'medium' | 'large'
export type StepGraphBackgroundKind = 'grid' | 'solid' | 'image'

export interface StepGraphPosition {
  x: number
  y: number
}

export interface StepGraphNode {
  id: StepStructurePath
  path: StepStructurePath
  kind: StepGraphNodeKind
  parentPath: StepStructurePath | null
  order: number
  label: string
  detail: string
  typeLabel: string
  summary: string
  stepType: StepType | null
  stepNo: number | null
  timeoutMs: number | null
  retryTimes: number | null
  errorCount: number
  editable: boolean
  readOnly: boolean
  branchKey: string | null
  componentId: number | null
  componentStatus: string | null
  hiddenDescendantCount: number
  position: StepGraphPosition
  width: number
  height: number
}

export interface StepGraphEdge {
  id: string
  source: StepStructurePath
  target: StepStructurePath
  kind: StepGraphEdgeKind
  label: string
  executable: boolean
  annotationOnly: boolean
}

export interface StepGraph {
  nodes: StepGraphNode[]
  edges: StepGraphEdge[]
}

export interface StepGraphComponentStep {
  name: string
  type: StepType
  summary?: string
  timeoutMs?: number
  retryTimes?: number
  errorCount?: number
}

export interface StepGraphComponentPreview {
  componentId: number
  name: string
  status: string
  steps: readonly StepGraphComponentStep[]
  loadState?: 'loading' | 'ready' | 'error'
  errorMessage?: string
}

export interface StepGraphAnnotation {
  id: string
  source: EditableStepPath
  target: EditableStepPath
  kind: StepGraphAnnotationKind
  label?: string
}

export interface StepGraphNodeDisplayState {
  position?: StepGraphPosition
  collapsed?: boolean
  color?: string
  shape?: StepGraphNodeShape
  size?: StepGraphNodeSize
}

export interface StepGraphBackgroundPreference {
  kind: StepGraphBackgroundKind
  color?: string
  imageKey?: string
  imageOpacity?: number
  imageFit?: 'cover' | 'contain' | 'repeat'
  imageFixed?: boolean
}

export interface StepGraphDisplayState {
  nodeStates: Record<string, StepGraphNodeDisplayState>
  annotations: StepGraphAnnotation[]
  connectionStyle: StepGraphConnectionStyle
  background: StepGraphBackgroundPreference
}

export interface StepGraphProjectionOptions {
  rootLabel?: string
  componentPreviews?: Readonly<Record<number, StepGraphComponentPreview>>
  annotations?: readonly StepGraphAnnotation[]
}

export interface StepGraphLayoutOptions {
  rankSeparation?: number
  nodeSeparation?: number
  edgeSeparation?: number
  marginX?: number
  marginY?: number
}

export type StepPathMigration = Readonly<Record<string, StepStructurePath>>

export interface StepGraphMutationResult<TDraft> {
  drafts: TDraft[]
  pathMigration: StepPathMigration
  focusPath: EditableStepPath | null
}

export type StepGraphOperationErrorCode =
  | 'INVALID_PATH'
  | 'INVALID_INDEX'
  | 'INVALID_NESTING'
  | 'EMPTY_BRANCH'
  | 'READ_ONLY_PATH'

export type StepGraphDropOperation = 'move' | 'reorder' | 'none'

export interface StepGraphDropAssessment {
  valid: boolean
  operation: StepGraphDropOperation
  reason: string
  sourcePath: StepStructurePath
  targetContainerPath: StepContainerPath
  insertionIndex: number
}

export interface StepGraphInsertionAssessment {
  valid: boolean
  reason: string
  targetContainerPath: StepContainerPath
  insertionIndex: number
}

export interface StepGraphEdgeVisual {
  color: string
  dasharray: string | null
  arrow: 'closed' | 'open' | 'none'
  doubleTrack: boolean
}
