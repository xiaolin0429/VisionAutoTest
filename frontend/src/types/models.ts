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
  tokenType: string
  expiresIn: number
  issuedAt: number
  user: User
}

export interface SessionRefreshPayload {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
  issuedAt: number
}

export type SessionCheckStatus = 'idle' | 'checking' | 'valid' | 'invalid'

export interface CurrentSession {
  sessionId: string
  status: string
  expiresAt: string
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

export interface ExecutionReadinessIssue {
  code: string
  message: string
  resourceType: string
  resourceId: number | null
  resourceName: string
  routePath: string | null
}

export interface ExecutionReadinessSummary {
  scope: 'workspace' | 'test_suite'
  status: 'ready' | 'blocked'
  workspaceId: number
  testSuiteId: number | null
  activeEnvironmentCount: number
  activeTestSuiteCount: number
  blockingIssueCount: number
  issues: ExecutionReadinessIssue[]
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

export interface EnvironmentProfileCreatePayload {
  name: string
  baseUrl: string
  description?: string
  status: string
}

export interface EnvironmentProfileUpdatePayload {
  name?: string
  baseUrl?: string
  description?: string
  status?: string
}

export interface EnvironmentVariable {
  id: number
  environmentProfileId: number
  key: string
  isSecret: boolean
  description: string
  displayValue: string
  createdAt: string
  updatedAt: string
}

export interface EnvironmentVariableCreatePayload {
  key: string
  value: string
  isSecret: boolean
  description?: string
}

export interface EnvironmentVariableUpdatePayload {
  value?: string
  isSecret?: boolean
  description?: string
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

export interface DeviceProfileCreatePayload {
  name: string
  platform: string
  width: number
  height: number
  pixelRatio: number
  userAgent?: string
  isDefault: boolean
}

export interface DeviceProfileUpdatePayload {
  name?: string
  platform?: string
  width?: number
  height?: number
  pixelRatio?: number
  userAgent?: string
  isDefault?: boolean
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
  steps?: Step[]
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

export type TemplateWorkbenchViewMode = 'original' | 'ocr' | 'mask' | 'processed'

export interface TemplateOcrPoint {
  x: number
  y: number
}

export interface TemplateOcrPixelRect {
  x: number
  y: number
  width: number
  height: number
}

export interface TemplateOcrRatioRect {
  xRatio: number
  yRatio: number
  widthRatio: number
  heightRatio: number
}

export interface TemplateOcrResult {
  id: number | null
  templateId: number
  baselineRevisionId: number
  sourceMediaObjectId: number
  status: string
  engineName: string
  imageWidth: number | null
  imageHeight: number | null
  errorCode: string | null
  errorMessage: string | null
  createdAt: string | null
  updatedAt: string | null
  blocks: TemplateOcrBlock[]
}

export interface TemplateOcrBlock {
  id: string
  text: string
  confidence: number
  orderNo: number
  polygonPoints: TemplateOcrPoint[]
  pixelRect: TemplateOcrPixelRect
  ratioRect: TemplateOcrRatioRect
  highlighted: boolean
}

export interface TemplatePreviewState {
  status: 'idle' | 'loading' | 'ready' | 'unavailable' | 'error'
  baselineRevisionId: number | null
  sourceMediaObjectId: number | null
  overlayMediaObjectId: number | null
  overlayImageUrl: string | null
  processedMediaObjectId: number | null
  processedImageUrl: string | null
  imageWidth: number | null
  imageHeight: number | null
  maskRegions: MaskRegion[]
  message: string
}

export interface TemplateOcrPanelState {
  status: 'idle' | 'loading' | 'not_generated' | 'ready' | 'error'
  baselineRevisionId: number | null
  message: string
}

export type StepType =
  | 'wait'
  | 'click'
  | 'input'
  | 'template_assert'
  | 'ocr_assert'
  | 'component_call'
  | 'navigate'
  | 'scroll'
  | 'long_press'

export type NavigateWaitUntil = 'load' | 'domcontentloaded' | 'networkidle'

export type ScrollTargetType = 'page' | 'element'

export type ScrollDirection = 'up' | 'down' | 'left' | 'right'

export type ScrollBehaviorMode = 'auto' | 'smooth'

export type LongPressButton = 'left'

export type OcrAssertMatchMode = 'exact' | 'contains'

export type LocatorType = 'selector' | 'ocr' | 'visual'

export type OcrLocatorMatchMode = 'exact' | 'contains'

export type InputMode = 'fill' | 'type' | 'otp'

export interface Step {
  id: number
  stepNo: number
  name: string
  type: StepType
  templateId: number | null
  componentId: number | null
  target: string
  note: string
  payloadJson: Record<string, unknown>
  timeoutMs: number
  retryTimes: number
}

export interface StepWritePayload {
  stepNo: number
  type: StepType
  name: string
  templateId: number | null
  componentId: number | null
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

export interface TestCaseCreatePayload {
  code: string
  name: string
  status: string
  priority: string
  description?: string
}

export interface TestCaseUpdatePayload {
  name?: string
  status?: string
  priority?: string
  description?: string
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

export interface TestSuiteCreatePayload {
  code: string
  name: string
  status: string
  description?: string
}

export interface TestSuiteUpdatePayload {
  name?: string
  status?: string
  description?: string
}

export interface SuiteCaseWritePayload {
  testCaseId: number
  sortOrder: number
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
  repairResourceType: 'template' | 'component' | 'test_case' | null
  repairResourceId: number | null
  repairRoutePath: string | null
  repairStepNo: number | null
}

export interface ReportArtifact {
  id: number
  reportId: number
  artifactType: string
  mediaObjectId: number | null
  caseRunId: number | null
  stepResultId: number | null
  artifactUrl: string | null
  createdAt: string
}

export interface ReportSummaryCounts {
  total: number
  passed: number
  failed: number
  error: number
  cancelled: number
}

export interface ReportSummaryFailure {
  code: string | null
  summary: string | null
}

export interface ReportSummaryTiming {
  startedAt: string | null
  finishedAt: string | null
  durationMs: number | null
}

export interface ReportSummaryArtifacts {
  total: number
  byType: Record<string, number>
}

export interface ReportSummary {
  status: string
  counts: ReportSummaryCounts
  failure: ReportSummaryFailure | null
  timing: ReportSummaryTiming
  artifacts: ReportSummaryArtifacts
  totalCaseCount: number
  passedCaseCount: number
  failedCaseCount: number
  errorCaseCount: number
  cancelledCaseCount: number
  message: string | null
}

export interface RunReport {
  id: number
  testRunId: number
  status: string
  summary: ReportSummary
  generatedAt: string
  createdAt: string
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
  testSuiteId: number
  environmentProfileId: number
  deviceProfileId: number | null
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
