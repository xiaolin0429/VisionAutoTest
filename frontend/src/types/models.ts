export type LifecycleStatus =
  | 'active'
  | 'inactive'
  | 'archived'
  | 'draft'
  | 'published'
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'cancelled'
  | 'passed'
  | 'failed'
  | 'partial_failed'
  | 'error'
  | 'pending'
  | 'skipped'
  | (string & {})

export interface User {
  id: number
  username: string
  displayName: string
  email?: string
  status?: string
}

export interface SessionPayload {
  sessionId: string
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: User
}

export interface Workspace {
  id: number
  ownerUserId: number
  name: string
  code: string
  description: string
  status: string
  memberCount: number
  role: string
  createdAt: string
  updatedAt: string
}

export interface EnvironmentProfile {
  id: number
  workspaceId: number
  name: string
  baseUrl: string
  description: string
  status: string
  variableCount: number
  createdAt: string
  updatedAt: string
}

export interface DeviceProfile {
  id: number
  workspaceId: number
  name: string
  platform: string
  width: number
  height: number
  pixelRatio: number
  userAgent?: string
  isDefault: boolean
  createdAt: string
  updatedAt: string
}

export interface Component {
  id: number
  workspaceId: number
  code: string
  name: string
  status: string
  description: string
  publishedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface MediaObject {
  id: number
  workspaceId: number
  storageType: string
  bucketName: string | null
  objectKey: string
  fileName: string
  mimeType: string
  fileSize: number
  checksumSha256: string
  status: string
  usage: string
  remark: string
  createdAt: string
}

export interface MaskRegion {
  id: number
  name: string
  xRatio: number
  yRatio: number
  widthRatio: number
  heightRatio: number
  sortOrder: number
}

export interface TemplateMaskDraft extends MaskRegion {
  isNew?: boolean
}

export interface TemplateMaskCreatePayload {
  name: string
  xRatio: number
  yRatio: number
  widthRatio: number
  heightRatio: number
  sortOrder: number
}

export interface TemplateMaskUpdatePayload {
  name?: string
  xRatio?: number
  yRatio?: number
  widthRatio?: number
  heightRatio?: number
  sortOrder?: number
}

export interface BaselineRevision {
  id: number
  templateId: number
  revisionNo: number
  mediaObjectId: number
  sourceType: string
  isCurrent: boolean
  remark: string
  createdAt: string
}

export interface TemplateCreatePayload {
  code: string
  name: string
  templateType: string
  matchStrategy: string
  thresholdValue: number
  status: string
  originalMediaObjectId: number
}

export interface TemplateUpdatePayload {
  name?: string
  templateType?: string
  matchStrategy?: string
  thresholdValue?: number
  status?: string
}

export interface BaselineRevisionCreatePayload {
  mediaObjectId: number
  sourceType: string
  remark?: string
  isCurrent: boolean
}

export type TemplateEditorMode = 'view' | 'edit'

export type TemplateCanvasInteractionHandle = 'move' | 'nw' | 'ne' | 'sw' | 'se'

export interface Template {
  id: number
  code: string
  name: string
  templateType: string
  matchStrategy: string
  thresholdValue: number
  status: string
  currentBaselineRevisionId: number | null
  baselineVersion: string
  createdAt: string
  updatedAt: string
  imageLabel: string
  baselineRevisions: BaselineRevision[]
  maskRegions: MaskRegion[]
}

export interface Step {
  id: number
  stepNo: number
  name: string
  type: string
  templateId: number | null
  componentId: number | null
  target: string
  note: string
  payloadJson: Record<string, unknown>
  timeoutMs: number
  retryTimes: number
}

export interface TestCase {
  id: number
  code: string
  name: string
  status: string
  priority: string
  description: string
  createdAt: string
  updatedAt: string
  componentCount: number
  steps: Step[]
}

export interface SuiteCase {
  id: number
  testCaseId: number
  name: string
  orderNo: number
  status: string
  createdAt?: string
}

export interface TestSuite {
  id: number
  code: string
  name: string
  status: string
  description: string
  createdAt: string
  updatedAt: string
  cases: SuiteCase[]
}

export type TestRunStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'cancelled'
  | 'passed'
  | 'failed'
  | 'partial_failed'
  | 'error'

export type CaseRunStatus =
  | 'pending'
  | 'running'
  | 'passed'
  | 'failed'
  | 'error'
  | 'skipped'
  | 'cancelled'

export interface TestRun {
  id: number
  testSuiteId: number
  suiteName: string
  environmentProfileId: number
  environmentName: string
  deviceProfileId: number | null
  deviceName: string
  status: string
  triggerSource: string
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  totalCaseCount: number
  passedCaseCount: number
  failedCaseCount: number
  errorCaseCount: number
}

export interface StepResult {
  id: number
  stepNo: number
  name: string
  type: string
  status: string
  message: string
  durationMs: number | null
  scoreValue: number | null
  expectedMediaObjectId: number | null
  actualMediaObjectId: number | null
  diffMediaObjectId: number | null
  artifactLabel?: string
}

export interface CaseRun {
  id: number
  testCaseId: number
  name: string
  status: string
  durationMs: number
  diffCount: number
  failureSummary: string
  sortOrder: number
  steps: StepResult[]
}

export interface RunSummary {
  totalCases: number
  passedCases: number
  failedCases: number
  errorCases: number
  durationSeconds: number
}

export interface RunDetail {
  id: number
  testRunId: number
  suiteName: string
  environmentName: string
  deviceName: string
  status: string
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  summary: RunSummary
  caseRuns: CaseRun[]
}
