import type {
  EditableStepPath,
  StepGraphConnectionStyle,
  StepGraphEdge,
  StepGraphEdgeVisual,
  StepGraphNode,
  StepGraphNodeShape,
  StepStructurePath
} from '@/types/stepGraph'
import type { StepType } from '@/types/models'

export const STEP_CANVAS_PALETTE_MIME = 'application/x-visionautotest-step-type'

export interface StepCanvasPaletteDragPayload {
  stepType: StepType
}

export interface StepCanvasNodePalette {
  background: string
  border: string
}

export interface StepCanvasNodeData {
  graphNode: StepGraphNode
  palette: StepCanvasNodePalette
  shape: StepGraphNodeShape
  collapsed: boolean
  canCollapse: boolean
  onToggleCollapse: (path: StepStructurePath) => void
  onAddAfter: (path: EditableStepPath) => void
  onDuplicate: (path: EditableStepPath) => void
  onMore: (path: EditableStepPath) => void
  onOpenInspector: (path: StepStructurePath) => void
  onOpenComponent: (componentId: number) => void
}

export interface StepCanvasEdgeData {
  graphEdge: StepGraphEdge
  visual: StepGraphEdgeVisual
  connectionStyle: StepGraphConnectionStyle
  showLabel: boolean
  title: string
}

export type StepCanvasStepsChangeKind =
  | 'create'
  | 'move'
  | 'reorder'
  | 'duplicate'
  | 'delete'
  | 'paste'
  | 'cut'

export interface StepCanvasStepsChange {
  kind: StepCanvasStepsChangeKind
  sourcePath: EditableStepPath
  targetContainerPath?: StepStructurePath
  insertionIndex?: number
  focusPath: EditableStepPath | null
}

export interface StepCanvasValidationError {
  path: EditableStepPath
  nodeLabel: string
  messages: string[]
}
