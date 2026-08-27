import type {
  InputMode,
  LocatorType,
  LongPressButton,
  NavigateWaitUntil,
  OcrActionPoint,
  OcrAssertionMode,
  OcrAssertionScope,
  OcrAssertMatchMode,
  OcrElementRole,
  OcrLanguageProfile,
  OcrLocatorMatchMode,
  OcrRelationType,
  OcrTargetPayload,
  OcrTargetScope,
  ScrollBehaviorMode,
  ScrollDirection,
  ScrollTargetType,
  Step,
  StepType,
  StepWritePayload
} from '@/types/models'

interface StepSummarySource {
  type: StepType
  payloadJson: Record<string, unknown>
  templateId: number | null
  componentId: number | null
  timeoutMs: number
  retryTimes: number
}

export type ConditionalBranchConditionType =
  | 'ocr_text_visible'
  | 'template_visible'
  | 'selector_exists'

export interface OcrTargetRelationDraft {
  type: OcrRelationType
  anchorText: string
  maxDistanceRatio: number
}

export interface OcrTargetDraft {
  text: string
  matchMode: OcrLocatorMatchMode
  caseSensitive: boolean
  occurrence: number
  scope: OcrTargetScope
  language: OcrLanguageProfile
  role: OcrElementRole
  minConfidence: number
  minScore: number
  ambiguityMargin: number
  actionPoint: OcrActionPoint
  relation: OcrTargetRelationDraft | null
}

export interface OcrTargetValidationErrors {
  text?: string
  matchMode?: string
  occurrence?: string
  scope?: string
  language?: string
  role?: string
  minConfidence?: string
  minScore?: string
  ambiguityMargin?: string
  actionPoint?: string
  relationType?: string
  relationAnchorText?: string
  relationMaxDistanceRatio?: string
}

export interface ConditionalBranchDraft {
  id: number
  branchKey: string
  branchName: string
  conditionType: ConditionalBranchConditionType
  ocrTarget: OcrTargetDraft
  templateId: number | null
  threshold: number | null
  selector: string
  steps: StepDraft[]
}

export interface StepDraft {
  id: number
  stepNo: number
  name: string
  type: StepType
  templateId: number | null
  componentId: number | null
  waitMs: number | null
  selector: string
  visualTemplateId: number | null
  visualThreshold: number | null
  visualAnchorXRatio: number | null
  visualAnchorYRatio: number | null
  text: string
  inputMode: InputMode
  otpLength: number | null
  perCharDelayMs: number | null
  threshold: number | null
  ocrAssertionScope: OcrAssertionScope
  ocrAssertionMode: OcrAssertionMode
  ocrExpectedCount: number | null
  url: string
  waitUntil: NavigateWaitUntil
  scrollTarget: ScrollTargetType
  direction: ScrollDirection
  distance: number | null
  behavior: ScrollBehaviorMode
  durationMs: number | null
  button: LongPressButton
  locator: LocatorType
  ocrTarget: OcrTargetDraft
  fieldTarget: OcrTargetDraft
  optionTarget: OcrTargetDraft
  verifySelected: boolean
  extraPayloadJson: string
  timeoutMs: number
  retryTimes: number
  conditionalBranches: ConditionalBranchDraft[]
  elseBranchEnabled: boolean
  elseBranchName: string
  elseSteps: StepDraft[]
}

export interface StepValidationErrors {
  waitMs?: string
  selector?: string
  visualTemplateId?: string
  visualThreshold?: string
  visualAnchorXRatio?: string
  visualAnchorYRatio?: string
  text?: string
  inputMode?: string
  otpLength?: string
  perCharDelayMs?: string
  templateId?: string
  threshold?: string
  ocrAssertionScope?: string
  ocrAssertionMode?: string
  ocrExpectedCount?: string
  componentId?: string
  timeoutMs?: string
  retryTimes?: string
  extraPayloadJson?: string
  url?: string
  waitUntil?: string
  scrollTarget?: string
  direction?: string
  distance?: string
  behavior?: string
  durationMs?: string
  button?: string
  ocrTarget?: string
  fieldTarget?: string
  optionTarget?: string
}

export interface StepTemplateOption {
  id: number
  label: string
}

export type StepFieldErrorGetter = (field: keyof StepValidationErrors) => string

export interface StepTypeOption {
  label: string
  value: StepType
}

export const STEP_TYPE_LABELS: Record<StepType, string> = {
  wait: '等待',
  click: '点击',
  input: '输入',
  select_option: 'OCR 选择',
  template_assert: '模板断言',
  ocr_assert: 'OCR 断言',
  component_call: '组件调用',
  navigate: '访问页面',
  scroll: '滑动',
  long_press: '长按',
  conditional_branch: '条件分支'
}

export const OCR_MATCH_MODE_OPTIONS: Array<{ label: string; value: OcrAssertMatchMode }> = [
  { label: '包含', value: 'contains' },
  { label: '完全匹配', value: 'exact' },
  { label: '正则表达式', value: 'regex' },
  { label: '模糊匹配', value: 'fuzzy' }
]

export const OCR_TARGET_SCOPE_OPTIONS: Array<{ label: string; value: OcrTargetScope }> = [
  { label: '当前视口', value: 'viewport' },
  { label: '整页分段扫描', value: 'page' }
]

export const OCR_ASSERTION_SCOPE_OPTIONS: Array<{
  label: string
  value: OcrAssertionScope
}> = [
  ...OCR_TARGET_SCOPE_OPTIONS,
  { label: '兼容元素区域', value: 'element_legacy' }
]

export const OCR_ASSERTION_MODE_OPTIONS: Array<{
  label: string
  value: OcrAssertionMode
}> = [
  { label: '存在', value: 'present' },
  { label: '不存在', value: 'absent' },
  { label: '数量', value: 'count' },
  { label: '关系', value: 'relation' }
]

export const OCR_LANGUAGE_OPTIONS: Array<{ label: string; value: OcrLanguageProfile }> = [
  { label: '自动', value: 'auto' },
  { label: '中英混合', value: 'zh_en' },
  { label: '英文', value: 'en' },
  { label: '拉丁字符', value: 'latin' },
  { label: '日文', value: 'japan' },
  { label: '韩文', value: 'korean' }
]

export const OCR_ROLE_OPTIONS: Array<{ label: string; value: OcrElementRole }> = [
  { label: '不限', value: 'any' },
  { label: '普通文字', value: 'text' },
  { label: '按钮', value: 'button' },
  { label: '输入区域', value: 'input' },
  { label: '菜单项', value: 'menu_item' },
  { label: '标签', value: 'label' }
]

export const OCR_ACTION_POINT_OPTIONS: Array<{ label: string; value: OcrActionPoint }> = [
  { label: '文字中心', value: 'text_center' },
  { label: '关联控件中心', value: 'associated_control' }
]

export const OCR_RELATION_TYPE_OPTIONS: Array<{ label: string; value: OcrRelationType }> = [
  { label: '位于锚点左侧', value: 'left_of' },
  { label: '位于锚点右侧', value: 'right_of' },
  { label: '位于锚点上方', value: 'above' },
  { label: '位于锚点下方', value: 'below' },
  { label: '离锚点最近', value: 'nearest' },
  { label: '与锚点同行', value: 'same_row' },
  { label: '与锚点同列', value: 'same_column' },
  { label: '锚点关联控件', value: 'associated_control' }
]

export const NAVIGATE_WAIT_UNTIL_OPTIONS: Array<{ label: string; value: NavigateWaitUntil }> = [
  { label: 'load', value: 'load' },
  { label: 'domcontentloaded', value: 'domcontentloaded' },
  { label: 'networkidle', value: 'networkidle' }
]

export const SCROLL_TARGET_OPTIONS: Array<{ label: string; value: ScrollTargetType }> = [
  { label: '页面', value: 'page' },
  { label: '元素', value: 'element' }
]

export const SCROLL_DIRECTION_OPTIONS: Array<{ label: string; value: ScrollDirection }> = [
  { label: '向上', value: 'up' },
  { label: '向下', value: 'down' },
  { label: '向左', value: 'left' },
  { label: '向右', value: 'right' }
]

export const SCROLL_BEHAVIOR_OPTIONS: Array<{ label: string; value: ScrollBehaviorMode }> = [
  { label: 'auto', value: 'auto' },
  { label: 'smooth', value: 'smooth' }
]

export const LONG_PRESS_BUTTON_OPTIONS: Array<{ label: string; value: LongPressButton }> = [
  { label: 'left', value: 'left' }
]

export const LOCATOR_TYPE_OPTIONS: Array<{ label: string; value: LocatorType }> = [
  { label: 'CSS 选择器', value: 'selector' },
  { label: 'OCR 文字定位', value: 'ocr' },
  { label: '视觉模板定位', value: 'visual' }
]

export const OCR_LOCATOR_MATCH_MODE_OPTIONS: Array<{ label: string; value: OcrLocatorMatchMode }> = [
  ...OCR_MATCH_MODE_OPTIONS
]

export const INPUT_MODE_OPTIONS: Array<{ label: string; value: InputMode }> = [
  { label: '普通输入', value: 'fill' },
  { label: '键盘输入', value: 'type' },
  { label: '验证码输入', value: 'otp' }
]

export const CONDITIONAL_BRANCH_CONDITION_OPTIONS: Array<{
  label: string
  value: ConditionalBranchConditionType
}> = [
  { label: 'OCR 文本可见', value: 'ocr_text_visible' },
  { label: '模板可见', value: 'template_visible' },
  { label: '选择器存在', value: 'selector_exists' }
]

const DEFAULT_WAIT_MS = 200
const DEFAULT_TIMEOUT_MS = 15000
const DEFAULT_SCROLL_DISTANCE = 1200
const DEFAULT_LONG_PRESS_DURATION_MS = 800
const DEFAULT_INPUT_MODE: InputMode = 'fill'
const DEFAULT_OTP_PER_CHAR_DELAY_MS = 80
const DEFAULT_VISUAL_ANCHOR_RATIO = 0.5
const DEFAULT_OCR_MIN_CONFIDENCE = 0.75
const DEFAULT_OCR_MIN_SCORE = 0.75
const DEFAULT_OCR_AMBIGUITY_MARGIN = 0.1

export function createOcrTargetDraft(
  overrides: Partial<OcrTargetDraft> = {}
): OcrTargetDraft {
  return {
    text: '',
    matchMode: 'exact',
    caseSensitive: false,
    occurrence: 1,
    scope: 'viewport',
    language: 'zh_en',
    role: 'any',
    minConfidence: DEFAULT_OCR_MIN_CONFIDENCE,
    minScore: DEFAULT_OCR_MIN_SCORE,
    ambiguityMargin: DEFAULT_OCR_AMBIGUITY_MARGIN,
    actionPoint: 'text_center',
    relation: null,
    ...overrides
  }
}

function createConditionalBranchDraft(index: number): ConditionalBranchDraft {
  // @param index Zero-based branch index used for draft ids, default labels, and branch keys.
  return {
    id: -Date.now() - index,
    branchKey: `branch_${index + 1}`,
    branchName: `分支 ${index + 1}`,
    conditionType: 'ocr_text_visible',
    ocrTarget: createOcrTargetDraft(),
    templateId: null,
    threshold: null,
    selector: '',
    steps: [createBranchChildStepDraft(0)]
  }
}

export function createBranchChildStepDraft(index: number): StepDraft {
  // @param index Zero-based child-step index used to seed stepNo and stable draft ids.
  return {
    id: -Date.now() - index,
    stepNo: index + 1,
    name: '',
    type: 'wait',
    templateId: null,
    componentId: null,
    waitMs: DEFAULT_WAIT_MS,
    selector: '',
    visualTemplateId: null,
    visualThreshold: null,
    visualAnchorXRatio: DEFAULT_VISUAL_ANCHOR_RATIO,
    visualAnchorYRatio: DEFAULT_VISUAL_ANCHOR_RATIO,
    text: '',
    inputMode: DEFAULT_INPUT_MODE,
    otpLength: null,
    perCharDelayMs: DEFAULT_OTP_PER_CHAR_DELAY_MS,
    threshold: null,
    ocrAssertionScope: 'viewport',
    ocrAssertionMode: 'present',
    ocrExpectedCount: null,
    url: '',
    waitUntil: 'load',
    scrollTarget: 'page',
    direction: 'down',
    distance: DEFAULT_SCROLL_DISTANCE,
    behavior: 'auto',
    durationMs: DEFAULT_LONG_PRESS_DURATION_MS,
    button: 'left',
    locator: 'selector',
    ocrTarget: createOcrTargetDraft(),
    fieldTarget: createOcrTargetDraft({
      role: 'input',
      actionPoint: 'associated_control'
    }),
    optionTarget: createOcrTargetDraft({
      role: 'menu_item'
    }),
    verifySelected: true,
    extraPayloadJson: '{}',
    timeoutMs: DEFAULT_TIMEOUT_MS,
    retryTimes: 0,
    conditionalBranches: [],
    elseBranchEnabled: false,
    elseBranchName: '默认分支',
    elseSteps: []
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function hasOwn(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key)
}

function isNavigateWaitUntil(value: unknown): value is NavigateWaitUntil {
  return value === 'load' || value === 'domcontentloaded' || value === 'networkidle'
}

function isSupportedNavigateUrl(value: string) {
  // @param value User-entered navigate target that may be a relative path or absolute URL.
  const normalized = value.trim()
  if (!normalized) {
    return false
  }

  if (normalized.startsWith('/')) {
    return true
  }

  try {
    const parsed = new URL(normalized)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

function isScrollTarget(value: unknown): value is ScrollTargetType {
  return value === 'page' || value === 'element'
}

function isScrollDirection(value: unknown): value is ScrollDirection {
  return value === 'up' || value === 'down' || value === 'left' || value === 'right'
}

function isScrollBehavior(value: unknown): value is ScrollBehaviorMode {
  return value === 'auto' || value === 'smooth'
}

function isLongPressButton(value: unknown): value is LongPressButton {
  return value === 'left'
}

function isLocatorType(value: unknown): value is LocatorType {
  return value === 'selector' || value === 'ocr' || value === 'visual'
}

function isOcrLocatorMatchMode(value: unknown): value is OcrLocatorMatchMode {
  return value === 'exact' || value === 'contains' || value === 'regex' || value === 'fuzzy'
}

function isOcrTargetScope(value: unknown): value is OcrTargetScope {
  return value === 'viewport' || value === 'page'
}

function isOcrAssertionScope(value: unknown): value is OcrAssertionScope {
  return isOcrTargetScope(value) || value === 'element_legacy'
}

function isOcrAssertionMode(value: unknown): value is OcrAssertionMode {
  return value === 'present' || value === 'absent' || value === 'count' || value === 'relation'
}

function isOcrLanguageProfile(value: unknown): value is OcrLanguageProfile {
  return (
    value === 'auto' ||
    value === 'zh_en' ||
    value === 'en' ||
    value === 'latin' ||
    value === 'japan' ||
    value === 'korean'
  )
}

function isOcrElementRole(value: unknown): value is OcrElementRole {
  return (
    value === 'any' ||
    value === 'text' ||
    value === 'button' ||
    value === 'input' ||
    value === 'menu_item' ||
    value === 'label'
  )
}

function isOcrActionPoint(value: unknown): value is OcrActionPoint {
  return value === 'text_center' || value === 'associated_control'
}

function isOcrRelationType(value: unknown): value is OcrRelationType {
  return (
    value === 'left_of' ||
    value === 'right_of' ||
    value === 'above' ||
    value === 'below' ||
    value === 'nearest' ||
    value === 'same_row' ||
    value === 'same_column' ||
    value === 'associated_control'
  )
}

function isInputMode(value: unknown): value is InputMode {
  return value === 'fill' || value === 'type' || value === 'otp'
}

function stringifyPayload(payload: Record<string, unknown>) {
  // @param payload Structured payload fields to be preserved in the advanced payload editor.
  const keys = Object.keys(payload)
  if (keys.length === 0) {
    return '{}'
  }

  return JSON.stringify(payload, null, 2)
}

function numberInRange(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function parseOcrTargetPayload(
  value: unknown,
  defaults: OcrTargetDraft = createOcrTargetDraft()
): OcrTargetDraft {
  if (!isRecord(value)) {
    return { ...defaults }
  }

  const relation = isRecord(value.relation)
    ? {
        type: isOcrRelationType(value.relation.type)
          ? value.relation.type
          : 'nearest',
        anchorText:
          typeof value.relation.anchor_text === 'string'
            ? value.relation.anchor_text
            : '',
        maxDistanceRatio: numberInRange(
          value.relation.max_distance_ratio,
          0.25
        )
      }
    : null

  return {
    text: typeof value.text === 'string' ? value.text : defaults.text,
    matchMode: isOcrLocatorMatchMode(value.match_mode)
      ? value.match_mode
      : defaults.matchMode,
    caseSensitive:
      typeof value.case_sensitive === 'boolean'
        ? value.case_sensitive
        : defaults.caseSensitive,
    occurrence:
      typeof value.occurrence === 'number' && Number.isFinite(value.occurrence)
        ? value.occurrence
        : defaults.occurrence,
    scope: isOcrTargetScope(value.scope) ? value.scope : defaults.scope,
    language: isOcrLanguageProfile(value.language)
      ? value.language
      : defaults.language,
    role: isOcrElementRole(value.role) ? value.role : defaults.role,
    minConfidence: numberInRange(value.min_confidence, defaults.minConfidence),
    minScore: numberInRange(value.min_score, defaults.minScore),
    ambiguityMargin: numberInRange(
      value.ambiguity_margin,
      defaults.ambiguityMargin
    ),
    actionPoint: isOcrActionPoint(value.action_point)
      ? value.action_point
      : defaults.actionPoint,
    relation
  }
}

function parseLocatorOcrTarget(payload: Record<string, unknown>): OcrTargetDraft {
  if (hasOwn(payload, 'ocr_target')) {
    return parseOcrTargetPayload(payload.ocr_target)
  }
  return parseOcrTargetPayload({
    text: payload.ocr_text,
    match_mode: isOcrLocatorMatchMode(payload.ocr_match_mode)
      ? payload.ocr_match_mode
      : 'contains',
    case_sensitive: payload.ocr_case_sensitive === true,
    occurrence: payload.ocr_occurrence,
    scope: 'viewport'
  })
}

export function buildOcrTargetPayload(
  target: OcrTargetDraft,
  scopeOverride?: OcrTargetScope
): OcrTargetPayload {
  return {
    text: target.text.trim(),
    match_mode: target.matchMode,
    case_sensitive: target.caseSensitive,
    occurrence: Number(target.occurrence),
    scope: scopeOverride ?? target.scope,
    language: target.language,
    role: target.role,
    min_confidence: Number(target.minConfidence),
    min_score: Number(target.minScore),
    ambiguity_margin: Number(target.ambiguityMargin),
    action_point: target.actionPoint,
    ...(target.relation
      ? {
          relation: {
            type: target.relation.type,
            anchor_text: target.relation.anchorText.trim(),
            max_distance_ratio: Number(target.relation.maxDistanceRatio)
          }
        }
      : {})
  }
}

function removeOcrLocatorPayload(payload: Record<string, unknown>): void {
  delete payload.ocr_target
  delete payload.ocr_text
  delete payload.ocr_match_mode
  delete payload.ocr_case_sensitive
  delete payload.ocr_occurrence
}

function formatTextValue(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) {
    return '--'
  }

  return value.trim()
}

function buildLocatorSummary(payload: Record<string, unknown>) {
  // @param payload Step payload used to build a readable locator summary in step overviews.
  const locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
  if (locator === 'ocr') {
    const target = parseLocatorOcrTarget(payload)
    const caseSensitive = target.caseSensitive ? '区分大小写' : '忽略大小写'

    return {
      locator,
      target: `OCR ${formatTextValue(target.text)}`,
      note: `${target.matchMode} · ${caseSensitive} · 第 ${target.occurrence} 个匹配 · ${target.scope} · ${target.language} · ${target.role}`
    }
  }

  if (locator === 'visual') {
    const anchorXRatio =
      typeof payload.anchor_x_ratio === 'number' ? payload.anchor_x_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
    const anchorYRatio =
      typeof payload.anchor_y_ratio === 'number' ? payload.anchor_y_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
    return {
      locator,
      target: `模板 #${typeof payload.template_id === 'number' ? payload.template_id : '--'}`,
      note: `视觉模板定位${typeof payload.threshold === 'number' ? ` · 阈值 ${payload.threshold.toFixed(2)}` : ''} · 点击锚点 (${(anchorXRatio * 100).toFixed(0)}%, ${(anchorYRatio * 100).toFixed(0)}%)`
    }
  }

  return {
    locator,
    target: formatTextValue(payload.selector),
    note: 'CSS 选择器'
  }
}

function formatExtraPayloadKeys(payload: Record<string, unknown>, knownKeys: string[]) {
  const extraKeys = Object.keys(payload).filter((key) => !knownKeys.includes(key))
  if (extraKeys.length === 0) {
    return ''
  }

  return ` · 扩展字段 ${extraKeys.join(', ')}`
}

function buildTimeoutAndRetry(timeoutMs: number, retryTimes: number) {
  return `超时 ${timeoutMs} ms · 重试 ${retryTimes}`
}

export function getStepTypeLabel(type: StepType) {
  return STEP_TYPE_LABELS[type]
}

export function createStepTypeOptions(options: { allowComponentCall: boolean }): StepTypeOption[] {
  // @param options.allowComponentCall Whether the caller supports component-call as a selectable step type.
  const values: StepType[] = [
    'wait',
    'click',
    'input',
    'select_option',
    'template_assert',
    'ocr_assert',
    'navigate',
    'scroll',
    'long_press',
    'conditional_branch'
  ]

  if (options.allowComponentCall) {
    values.push('component_call')
  }

  return values.map((value) => ({
    label: STEP_TYPE_LABELS[value],
    value
  }))
}

export function createEmptyStepDraft(index: number): StepDraft {
  // @param index Zero-based step index used to seed draft ids and initial `stepNo`.
  const draft = createBranchChildStepDraft(index)
  return {
    ...draft,
    conditionalBranches: [createConditionalBranchDraft(0)],
    elseSteps: [createBranchChildStepDraft(0)]
  }
}

export function normalizeStepDrafts(items: StepDraft[]) {
  // @param items Draft list whose `stepNo` values should be rewritten into continuous editor order.
  return items.map((item, index) => ({
    ...item,
    stepNo: index + 1
  }))
}

export function parseExtraPayloadJson(step: Pick<StepDraft, 'extraPayloadJson'>) {
  // @param step Step draft slice containing the raw advanced-payload JSON string.
  // @returns Parsed payload object or a validation error for the advanced payload editor.
  const raw = step.extraPayloadJson.trim()
  if (!raw) {
    return {
      value: {} as Record<string, unknown>
    }
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    if (isRecord(parsed)) {
      return {
        value: parsed
      }
    }
  } catch {
    return {
      error: '额外 payload 需要是合法 JSON。'
    }
  }

  return {
    error: '额外 payload 需要是 JSON 对象。'
  }
}

const STRUCTURED_PAYLOAD_KEYS = new Set([
  'ms',
  'locator',
  'selector',
  'template_id',
  'threshold',
  'anchor_x_ratio',
  'anchor_y_ratio',
  'ocr_target',
  'ocr_text',
  'ocr_match_mode',
  'ocr_case_sensitive',
  'ocr_occurrence',
  'field_target',
  'option_target',
  'verify_selected',
  'text',
  'input_mode',
  'otp_length',
  'per_char_delay_ms',
  'scope',
  'assertion',
  'expected_count',
  'expected_text',
  'match_mode',
  'case_sensitive',
  'url',
  'wait_until',
  'target',
  'direction',
  'distance',
  'behavior',
  'duration_ms',
  'button',
  'branches',
  'else_branch'
])

function sanitizeAdvancedPayload(raw: string): string {
  const parsed = parseExtraPayloadJson({ extraPayloadJson: raw })
  const value = 'value' in parsed ? parsed.value : undefined
  if (!value) {
    return '{}'
  }
  const sanitized = Object.fromEntries(
    Object.entries(value).filter(
      ([key]: [string, unknown]): boolean => !STRUCTURED_PAYLOAD_KEYS.has(key)
    )
  )
  return stringifyPayload(sanitized)
}

export function supportsOcrLocator(type: StepType): boolean {
  return type === 'click' || type === 'input' || type === 'scroll' || type === 'long_press'
}

export function normalizeStepByType(step: StepDraft, nextType: StepType): StepDraft {
  // @param step Existing draft that may contain fields from a previous step type.
  // @param nextType Target step type chosen by the user.
  // @returns A draft reshaped so only fields relevant to the target type remain active.
  if (step.type === nextType) {
    return { ...step }
  }

  const defaults = createEmptyStepDraft(step.stepNo - 1)
  return {
    ...defaults,
    id: step.id,
    stepNo: step.stepNo,
    name: step.name,
    type: nextType,
    extraPayloadJson: sanitizeAdvancedPayload(step.extraPayloadJson),
    timeoutMs: step.timeoutMs,
    retryTimes: step.retryTimes
  }
}

export function buildStepDraft(step: Step): StepDraft {
  // @param step Persisted backend step converted into the editor's richer draft structure.
  const payload = isRecord(step.payloadJson) ? { ...step.payloadJson } : {}
  const draft = createEmptyStepDraft(step.stepNo - 1)

  switch (step.type) {
    case 'wait':
      draft.waitMs =
        typeof payload.ms === 'number' && Number.isFinite(payload.ms) ? payload.ms : DEFAULT_WAIT_MS
      delete payload.ms
      break
    case 'click':
      draft.locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
      draft.selector = typeof payload.selector === 'string' ? payload.selector : ''
      draft.visualTemplateId = typeof payload.template_id === 'number' ? payload.template_id : null
      draft.visualThreshold = typeof payload.threshold === 'number' ? payload.threshold : null
      draft.visualAnchorXRatio =
        typeof payload.anchor_x_ratio === 'number' ? payload.anchor_x_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.visualAnchorYRatio =
        typeof payload.anchor_y_ratio === 'number' ? payload.anchor_y_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.ocrTarget = parseLocatorOcrTarget(payload)
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      removeOcrLocatorPayload(payload)
      break
    case 'input':
      draft.locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
      draft.selector = typeof payload.selector === 'string' ? payload.selector : ''
      draft.visualTemplateId = typeof payload.template_id === 'number' ? payload.template_id : null
      draft.visualThreshold = typeof payload.threshold === 'number' ? payload.threshold : null
      draft.visualAnchorXRatio =
        typeof payload.anchor_x_ratio === 'number' ? payload.anchor_x_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.visualAnchorYRatio =
        typeof payload.anchor_y_ratio === 'number' ? payload.anchor_y_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.text = typeof payload.text === 'string' ? payload.text : ''
      draft.inputMode = isInputMode(payload.input_mode) ? payload.input_mode : DEFAULT_INPUT_MODE
      draft.otpLength = typeof payload.otp_length === 'number' && payload.otp_length >= 1 ? payload.otp_length : null
      draft.perCharDelayMs =
        typeof payload.per_char_delay_ms === 'number' && payload.per_char_delay_ms >= 0
          ? payload.per_char_delay_ms
          : DEFAULT_OTP_PER_CHAR_DELAY_MS
      draft.ocrTarget = parseLocatorOcrTarget(payload)
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      delete payload.text
      delete payload.input_mode
      delete payload.otp_length
      delete payload.per_char_delay_ms
      removeOcrLocatorPayload(payload)
      break
    case 'select_option':
      draft.fieldTarget = parseOcrTargetPayload(
        payload.field_target,
        draft.fieldTarget
      )
      draft.optionTarget = parseOcrTargetPayload(
        payload.option_target,
        draft.optionTarget
      )
      draft.verifySelected = payload.verify_selected !== false
      delete payload.field_target
      delete payload.option_target
      delete payload.verify_selected
      break
    case 'template_assert':
      draft.threshold =
        typeof payload.threshold === 'number' && Number.isFinite(payload.threshold)
          ? payload.threshold
          : null
      delete payload.threshold
      break
    case 'ocr_assert':
      draft.selector = typeof payload.selector === 'string' ? payload.selector : ''
      draft.ocrAssertionScope = isOcrAssertionScope(payload.scope)
        ? payload.scope
        : draft.selector.trim()
          ? 'element_legacy'
          : isRecord(payload.ocr_target) && payload.ocr_target.scope === 'page'
            ? 'page'
            : 'viewport'
      draft.ocrAssertionMode = isOcrAssertionMode(payload.assertion)
        ? payload.assertion
        : 'present'
      draft.ocrExpectedCount =
        typeof payload.expected_count === 'number' &&
        Number.isFinite(payload.expected_count)
          ? payload.expected_count
          : null
      draft.ocrTarget = hasOwn(payload, 'ocr_target')
        ? parseOcrTargetPayload(payload.ocr_target)
        : parseOcrTargetPayload({
            text: payload.expected_text,
            match_mode:
              payload.match_mode === 'exact' ? 'exact' : 'contains',
            case_sensitive: payload.case_sensitive === true,
            scope: 'viewport'
          })
      delete payload.selector
      delete payload.scope
      delete payload.assertion
      delete payload.expected_count
      delete payload.ocr_target
      delete payload.expected_text
      delete payload.match_mode
      delete payload.case_sensitive
      break
    case 'navigate':
      draft.url = typeof payload.url === 'string' ? payload.url : ''
      draft.waitUntil = isNavigateWaitUntil(payload.wait_until) ? payload.wait_until : 'load'
      delete payload.url
      delete payload.wait_until
      break
    case 'scroll':
      draft.scrollTarget = isScrollTarget(payload.target) ? payload.target : 'page'
      draft.locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
      draft.selector = typeof payload.selector === 'string' ? payload.selector : ''
      draft.visualTemplateId = typeof payload.template_id === 'number' ? payload.template_id : null
      draft.visualThreshold = typeof payload.threshold === 'number' ? payload.threshold : null
      draft.visualAnchorXRatio =
        typeof payload.anchor_x_ratio === 'number' ? payload.anchor_x_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.visualAnchorYRatio =
        typeof payload.anchor_y_ratio === 'number' ? payload.anchor_y_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.direction = isScrollDirection(payload.direction) ? payload.direction : 'down'
      draft.distance =
        typeof payload.distance === 'number' && Number.isFinite(payload.distance)
          ? payload.distance
          : DEFAULT_SCROLL_DISTANCE
      draft.behavior = isScrollBehavior(payload.behavior) ? payload.behavior : 'auto'
      draft.ocrTarget = parseLocatorOcrTarget(payload)
      delete payload.target
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      delete payload.direction
      delete payload.distance
      delete payload.behavior
      removeOcrLocatorPayload(payload)
      break
    case 'long_press':
      draft.locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
      draft.selector = typeof payload.selector === 'string' ? payload.selector : ''
      draft.visualTemplateId = typeof payload.template_id === 'number' ? payload.template_id : null
      draft.visualThreshold = typeof payload.threshold === 'number' ? payload.threshold : null
      draft.visualAnchorXRatio =
        typeof payload.anchor_x_ratio === 'number' ? payload.anchor_x_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.visualAnchorYRatio =
        typeof payload.anchor_y_ratio === 'number' ? payload.anchor_y_ratio : DEFAULT_VISUAL_ANCHOR_RATIO
      draft.durationMs =
        typeof payload.duration_ms === 'number' && Number.isFinite(payload.duration_ms)
          ? payload.duration_ms
          : DEFAULT_LONG_PRESS_DURATION_MS
      draft.button = isLongPressButton(payload.button) ? payload.button : 'left'
      draft.ocrTarget = parseLocatorOcrTarget(payload)
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      delete payload.duration_ms
      delete payload.button
      removeOcrLocatorPayload(payload)
      break
    case 'component_call':
      break
    case 'conditional_branch':
      if (Array.isArray(payload.branches)) {
        draft.conditionalBranches = payload.branches
          .filter(isRecord)
          .map((branch, index) => {
            const condition = isRecord(branch.condition) ? branch.condition : {}
            const steps = Array.isArray(branch.steps) ? branch.steps : []
            return {
              id: -Date.now() - index,
              branchKey:
                typeof branch.branch_key === 'string' && branch.branch_key.trim()
                  ? branch.branch_key
                  : `branch_${index + 1}`,
              branchName:
                typeof branch.branch_name === 'string' && branch.branch_name.trim()
                  ? branch.branch_name
                  : `分支 ${index + 1}`,
              conditionType:
                condition.type === 'template_visible' || condition.type === 'selector_exists'
                  ? condition.type
                  : 'ocr_text_visible',
              ocrTarget: hasOwn(condition, 'ocr_target') || hasOwn(condition, 'ocr_text')
                ? parseLocatorOcrTarget(condition)
                : parseOcrTargetPayload({
                    text: condition.expected_text,
                    match_mode: isOcrLocatorMatchMode(condition.match_mode)
                      ? condition.match_mode
                      : 'contains',
                    case_sensitive: condition.case_sensitive === true,
                    scope: 'viewport'
                  }),
              templateId: typeof condition.template_id === 'number' ? condition.template_id : null,
              threshold: typeof condition.threshold === 'number' ? condition.threshold : null,
              selector: typeof condition.selector === 'string' ? condition.selector : '',
              steps: steps.map((item, stepIndex) =>
                buildStepDraft({
                  id: -Date.now() - stepIndex,
                  stepNo: stepIndex + 1,
                  name: typeof item.step_name === 'string' ? item.step_name : `子步骤 ${stepIndex + 1}`,
                  type: (typeof item.step_type === 'string' ? item.step_type : 'wait') as StepType,
                  templateId: typeof item.template_id === 'number' ? item.template_id : null,
                  componentId: null,
                  target: '',
                  note: '',
                  payloadJson: isRecord(item.payload_json) ? item.payload_json : {},
                  timeoutMs: typeof item.timeout_ms === 'number' ? item.timeout_ms : DEFAULT_TIMEOUT_MS,
                  retryTimes: typeof item.retry_times === 'number' ? item.retry_times : 0
                })
              )
            }
          })
      }
      if (isRecord(payload.else_branch)) {
        draft.elseBranchEnabled = payload.else_branch.enabled === true
        draft.elseBranchName =
          typeof payload.else_branch.branch_name === 'string'
            ? payload.else_branch.branch_name
            : '默认分支'
        draft.elseSteps = (Array.isArray(payload.else_branch.steps) ? payload.else_branch.steps : []).map(
          (item, stepIndex) =>
            buildStepDraft({
              id: -Date.now() - stepIndex,
              stepNo: stepIndex + 1,
              name: typeof item.step_name === 'string' ? item.step_name : `默认子步骤 ${stepIndex + 1}`,
              type: (typeof item.step_type === 'string' ? item.step_type : 'wait') as StepType,
              templateId: typeof item.template_id === 'number' ? item.template_id : null,
              componentId: null,
              target: '',
              note: '',
              payloadJson: isRecord(item.payload_json) ? item.payload_json : {},
              timeoutMs: typeof item.timeout_ms === 'number' ? item.timeout_ms : DEFAULT_TIMEOUT_MS,
              retryTimes: typeof item.retry_times === 'number' ? item.retry_times : 0
            })
        )
      }
      delete payload.branches
      delete payload.else_branch
      break
  }

  return {
    ...draft,
    id: step.id,
    stepNo: step.stepNo,
    name: step.name,
    type: step.type,
    templateId: step.templateId,
    componentId: step.componentId,
    extraPayloadJson: stringifyPayload(payload),
    timeoutMs: step.timeoutMs,
    retryTimes: step.retryTimes
  }
}

export function validateOcrTargetDraft(
  target: OcrTargetDraft
): OcrTargetValidationErrors {
  const errors: OcrTargetValidationErrors = {}
  if (!target.text.trim()) {
    errors.text = 'OCR 目标文字不能为空。'
  }
  if (!isOcrLocatorMatchMode(target.matchMode)) {
    errors.matchMode = 'OCR 匹配模式无效。'
  } else if (target.matchMode === 'regex' && target.text.trim()) {
    try {
      new RegExp(target.text)
    } catch {
      errors.text = 'OCR 正则表达式无效。'
    }
  }
  if (!Number.isInteger(target.occurrence) || target.occurrence < 1) {
    errors.occurrence = 'OCR 匹配序号必须为大于等于 1 的整数。'
  }
  if (!isOcrTargetScope(target.scope)) {
    errors.scope = 'OCR 扫描范围无效。'
  }
  if (!isOcrLanguageProfile(target.language)) {
    errors.language = 'OCR 语言档案无效。'
  }
  if (!isOcrElementRole(target.role)) {
    errors.role = 'OCR 角色提示无效。'
  }
  for (const [field, value, message] of [
    ['minConfidence', target.minConfidence, '最低 OCR 置信度必须在 0 到 1 之间。'],
    ['minScore', target.minScore, '最低综合分必须在 0 到 1 之间。'],
    ['ambiguityMargin', target.ambiguityMargin, '歧义分差必须在 0 到 1 之间。']
  ] as const) {
    if (!Number.isFinite(value) || value < 0 || value > 1) {
      errors[field] = message
    }
  }
  if (!isOcrActionPoint(target.actionPoint)) {
    errors.actionPoint = 'OCR 操作点无效。'
  }
  if (target.relation) {
    if (!isOcrRelationType(target.relation.type)) {
      errors.relationType = 'OCR 关系类型无效。'
    }
    if (!target.relation.anchorText.trim()) {
      errors.relationAnchorText = 'OCR 关系必须填写锚点文字。'
    }
    if (
      !Number.isFinite(target.relation.maxDistanceRatio) ||
      target.relation.maxDistanceRatio < 0 ||
      target.relation.maxDistanceRatio > 1
    ) {
      errors.relationMaxDistanceRatio = 'OCR 关系最大距离比例必须在 0 到 1 之间。'
    }
  }
  return errors
}

function firstOcrTargetError(target: OcrTargetDraft): string | undefined {
  return Object.values(validateOcrTargetDraft(target))[0]
}

function setOcrTargetError(
  errors: StepValidationErrors,
  field: 'ocrTarget' | 'fieldTarget' | 'optionTarget',
  target: OcrTargetDraft
): void {
  const error = firstOcrTargetError(target)
  if (error) {
    errors[field] = error
  }
}

export function validateStepDraft(step: StepDraft): StepValidationErrors {
  const errors: StepValidationErrors = {}

  if (!Number.isFinite(step.timeoutMs) || step.timeoutMs < 1) {
    errors.timeoutMs = '超时时间必须大于等于 1 ms。'
  }

  if (!Number.isFinite(step.retryTimes) || step.retryTimes < 0) {
    errors.retryTimes = '重试次数必须大于等于 0。'
  }

  const extraPayload = parseExtraPayloadJson(step)
  if ('error' in extraPayload) {
    errors.extraPayloadJson = extraPayload.error
  }

  switch (step.type) {
    case 'wait':
      if (!Number.isFinite(step.waitMs) || (step.waitMs ?? -1) < 0) {
        errors.waitMs = '等待时长必须大于等于 0 ms。'
      }
      break
    case 'click':
      if (step.locator === 'ocr') {
        setOcrTargetError(errors, 'ocrTarget', step.ocrTarget)
      } else if (step.locator === 'visual') {
        if (step.visualTemplateId === null) {
          errors.visualTemplateId = '点击步骤使用视觉模板定位时必须选择模板。'
        }
        if (step.visualThreshold !== null && (step.visualThreshold < 0 || step.visualThreshold > 1)) {
          errors.visualThreshold = '视觉定位阈值必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorXRatio === null ||
          !Number.isFinite(step.visualAnchorXRatio) ||
          step.visualAnchorXRatio < 0 ||
          step.visualAnchorXRatio > 1
        ) {
          errors.visualAnchorXRatio = '视觉锚点横向比例必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorYRatio === null ||
          !Number.isFinite(step.visualAnchorYRatio) ||
          step.visualAnchorYRatio < 0 ||
          step.visualAnchorYRatio > 1
        ) {
          errors.visualAnchorYRatio = '视觉锚点纵向比例必须在 0 到 1 之间。'
        }
      } else if (!step.selector.trim()) {
        errors.selector = '请选择或填写点击目标选择器。'
      }
      break
    case 'input':
      if (step.locator === 'ocr') {
        setOcrTargetError(errors, 'ocrTarget', step.ocrTarget)
      } else if (step.locator === 'visual') {
        if (step.visualTemplateId === null) {
          errors.visualTemplateId = '输入步骤使用视觉模板定位时必须选择模板。'
        }
        if (step.visualThreshold !== null && (step.visualThreshold < 0 || step.visualThreshold > 1)) {
          errors.visualThreshold = '视觉定位阈值必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorXRatio === null ||
          !Number.isFinite(step.visualAnchorXRatio) ||
          step.visualAnchorXRatio < 0 ||
          step.visualAnchorXRatio > 1
        ) {
          errors.visualAnchorXRatio = '视觉锚点横向比例必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorYRatio === null ||
          !Number.isFinite(step.visualAnchorYRatio) ||
          step.visualAnchorYRatio < 0 ||
          step.visualAnchorYRatio > 1
        ) {
          errors.visualAnchorYRatio = '视觉锚点纵向比例必须在 0 到 1 之间。'
        }
      } else if (!step.selector.trim()) {
        errors.selector = '请输入输入目标选择器。'
      }
      if (!step.text.trim()) {
        errors.text = '请输入要填充的文本。'
      }
      if (!isInputMode(step.inputMode)) {
        errors.inputMode = '输入方式仅支持 fill、type、otp。'
      }
      if (step.inputMode === 'otp') {
        if (!Number.isInteger(step.otpLength) || (step.otpLength ?? 0) < 1) {
          errors.otpLength = '验证码长度必须为大于等于 1 的整数。'
        } else if (step.text.trim() && step.text.trim().length !== step.otpLength) {
          errors.otpLength = '验证码长度必须与输入文本长度一致。'
        }
      }
      if (!Number.isFinite(step.perCharDelayMs) || (step.perCharDelayMs ?? -1) < 0) {
        errors.perCharDelayMs = '逐字符延迟必须大于等于 0 ms。'
      }
      break
    case 'select_option':
      setOcrTargetError(errors, 'fieldTarget', step.fieldTarget)
      setOcrTargetError(errors, 'optionTarget', step.optionTarget)
      break
    case 'template_assert':
      if (step.templateId === null) {
        errors.templateId = '模板断言必须选择模板。'
      }
      if (
        step.threshold !== null &&
        (!Number.isFinite(step.threshold) || step.threshold < 0 || step.threshold > 1)
      ) {
        errors.threshold = '阈值必须在 0 到 1 之间。'
      }
      break
    case 'ocr_assert':
      if (!isOcrAssertionScope(step.ocrAssertionScope)) {
        errors.ocrAssertionScope = 'OCR 断言范围无效。'
      }
      if (step.ocrAssertionScope === 'element_legacy' && !step.selector.trim()) {
        errors.selector = '兼容元素区域模式必须填写选择器。'
      }
      if (!isOcrAssertionMode(step.ocrAssertionMode)) {
        errors.ocrAssertionMode = 'OCR 断言模式无效。'
      }
      setOcrTargetError(errors, 'ocrTarget', step.ocrTarget)
      if (
        step.ocrAssertionMode === 'count' &&
        (!Number.isInteger(step.ocrExpectedCount) || (step.ocrExpectedCount ?? -1) < 0)
      ) {
        errors.ocrExpectedCount = 'OCR 期望数量必须为大于等于 0 的整数。'
      }
      if (step.ocrAssertionMode === 'relation' && !step.ocrTarget.relation) {
        errors.ocrTarget = '关系断言必须配置 OCR 相对关系。'
      }
      break
    case 'component_call':
      if (step.componentId === null) {
        errors.componentId = '组件调用必须选择组件。'
      }
      break
    case 'conditional_branch': {
      const branchKeys = new Set<string>()
      if (step.conditionalBranches.length === 0) {
        errors.extraPayloadJson = '条件分支至少需要 1 个分支。'
        break
      }
      if (step.conditionalBranches.length > 3) {
        errors.extraPayloadJson = '条件分支最多支持 3 个分支。'
        break
      }
      for (const branch of step.conditionalBranches) {
        if (!branch.branchKey.trim()) {
          errors.extraPayloadJson = '每个分支都必须填写 branchKey。'
          break
        }
        if (branchKeys.has(branch.branchKey.trim())) {
          errors.extraPayloadJson = 'branchKey 不能重复。'
          break
        }
        branchKeys.add(branch.branchKey.trim())
        if (!branch.branchName.trim()) {
          errors.extraPayloadJson = '每个分支都必须填写分支名称。'
          break
        }
        if (branch.conditionType === 'ocr_text_visible') {
          const targetError = firstOcrTargetError(branch.ocrTarget)
          if (targetError) {
            errors.extraPayloadJson = `OCR 文本可见条件无效：${targetError}`
            break
          }
        } else if (branch.conditionType === 'template_visible') {
          if (branch.templateId === null) {
            errors.extraPayloadJson = '模板可见条件必须选择模板。'
            break
          }
          if (
            branch.threshold !== null &&
            (!Number.isFinite(branch.threshold) || branch.threshold < 0 || branch.threshold > 1)
          ) {
            errors.extraPayloadJson = '模板条件阈值必须在 0 到 1 之间。'
            break
          }
        } else if (!branch.selector.trim()) {
          errors.extraPayloadJson = '选择器存在条件必须填写选择器。'
          break
        }
        if (branch.steps.length === 0) {
          errors.extraPayloadJson = '每个分支至少需要 1 个子步骤。'
          break
        }
        for (const childStep of branch.steps) {
          if (childStep.type === 'component_call' || childStep.type === 'conditional_branch') {
            errors.extraPayloadJson = '分支子步骤不支持 component_call 或 conditional_branch。'
            break
          }
          const childErrors = validateStepDraft(childStep)
          if (Object.keys(childErrors).length > 0) {
            errors.extraPayloadJson = '请先修正分支子步骤配置。'
            break
          }
        }
        if (errors.extraPayloadJson) break
      }
      if (!errors.extraPayloadJson && step.elseBranchEnabled) {
        if (step.elseSteps.length === 0) {
          errors.extraPayloadJson = '默认分支至少需要 1 个子步骤。'
        } else {
          for (const childStep of step.elseSteps) {
            if (childStep.type === 'component_call' || childStep.type === 'conditional_branch') {
              errors.extraPayloadJson = '默认分支子步骤不支持 component_call 或 conditional_branch。'
              break
            }
            const childErrors = validateStepDraft(childStep)
            if (Object.keys(childErrors).length > 0) {
              errors.extraPayloadJson = '请先修正默认分支子步骤配置。'
              break
            }
          }
        }
      }
      break
    }
    case 'navigate':
      if (!step.url.trim()) {
        errors.url = '访问页面必须填写 URL 或相对路径。'
      } else if (!isSupportedNavigateUrl(step.url)) {
        errors.url = 'URL 必须是 http/https 绝对地址，或以 / 开头的相对路径。'
      }
      if (!isNavigateWaitUntil(step.waitUntil)) {
        errors.waitUntil = '等待策略仅支持 load、domcontentloaded、networkidle。'
      }
      break
    case 'scroll':
      if (!isScrollTarget(step.scrollTarget)) {
        errors.scrollTarget = '滑动目标仅支持 page 或 element。'
      }
      if (step.scrollTarget === 'element') {
        if (step.locator === 'ocr') {
          setOcrTargetError(errors, 'ocrTarget', step.ocrTarget)
        } else if (step.locator === 'visual') {
          if (step.visualTemplateId === null) {
            errors.visualTemplateId = '元素滑动使用视觉模板定位时必须选择模板。'
          }
          if (step.visualThreshold !== null && (step.visualThreshold < 0 || step.visualThreshold > 1)) {
            errors.visualThreshold = '视觉定位阈值必须在 0 到 1 之间。'
          }
          if (
            step.visualAnchorXRatio === null ||
            !Number.isFinite(step.visualAnchorXRatio) ||
            step.visualAnchorXRatio < 0 ||
            step.visualAnchorXRatio > 1
          ) {
            errors.visualAnchorXRatio = '视觉锚点横向比例必须在 0 到 1 之间。'
          }
          if (
            step.visualAnchorYRatio === null ||
            !Number.isFinite(step.visualAnchorYRatio) ||
            step.visualAnchorYRatio < 0 ||
            step.visualAnchorYRatio > 1
          ) {
            errors.visualAnchorYRatio = '视觉锚点纵向比例必须在 0 到 1 之间。'
          }
        } else if (!step.selector.trim()) {
          errors.selector = '元素滑动必须填写选择器。'
        }
      }
      if (!isScrollDirection(step.direction)) {
        errors.direction = '滑动方向仅支持 up、down、left、right。'
      }
      if (!Number.isFinite(step.distance) || (step.distance ?? 0) <= 0) {
        errors.distance = '滑动距离必须大于 0 px。'
      }
      if (!isScrollBehavior(step.behavior)) {
        errors.behavior = '滑动行为仅支持 auto 或 smooth。'
      }
      break
    case 'long_press':
      if (step.locator === 'ocr') {
        setOcrTargetError(errors, 'ocrTarget', step.ocrTarget)
      } else if (step.locator === 'visual') {
        if (step.visualTemplateId === null) {
          errors.visualTemplateId = '长按步骤使用视觉模板定位时必须选择模板。'
        }
        if (step.visualThreshold !== null && (step.visualThreshold < 0 || step.visualThreshold > 1)) {
          errors.visualThreshold = '视觉定位阈值必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorXRatio === null ||
          !Number.isFinite(step.visualAnchorXRatio) ||
          step.visualAnchorXRatio < 0 ||
          step.visualAnchorXRatio > 1
        ) {
          errors.visualAnchorXRatio = '视觉锚点横向比例必须在 0 到 1 之间。'
        }
        if (
          step.visualAnchorYRatio === null ||
          !Number.isFinite(step.visualAnchorYRatio) ||
          step.visualAnchorYRatio < 0 ||
          step.visualAnchorYRatio > 1
        ) {
          errors.visualAnchorYRatio = '视觉锚点纵向比例必须在 0 到 1 之间。'
        }
      } else if (!step.selector.trim()) {
        errors.selector = '长按步骤必须填写选择器。'
      }
      if (!Number.isFinite(step.durationMs) || (step.durationMs ?? 0) <= 0) {
        errors.durationMs = '长按时长必须大于 0 ms。'
      }
      if (!isLongPressButton(step.button)) {
        errors.button = '当前仅支持 left 按钮。'
      }
      break
  }

  return errors
}

export function shouldOpenAdvancedPayload(step: StepDraft) {
  return step.extraPayloadJson.trim() !== '{}' || Boolean(validateStepDraft(step).extraPayloadJson)
}

function buildStructuredPayload(step: StepDraft): Record<string, unknown> {
  switch (step.type) {
    case 'wait':
      return {
        ms: Number(step.waitMs ?? 0)
      }
    case 'click':
      return step.locator === 'ocr'
        ? {
            locator: 'ocr',
            ocr_target: buildOcrTargetPayload(step.ocrTarget)
          }
        : step.locator === 'visual'
          ? {
              locator: 'visual',
              template_id: step.visualTemplateId,
              ...(step.visualThreshold !== null ? { threshold: Number(step.visualThreshold) } : {}),
              anchor_x_ratio: Number(step.visualAnchorXRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO),
              anchor_y_ratio: Number(step.visualAnchorYRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO)
            }
        : {
            selector: step.selector.trim()
          }
    case 'input':
      return {
        ...(step.locator === 'ocr'
          ? {
              locator: 'ocr',
              ocr_target: buildOcrTargetPayload(step.ocrTarget)
            }
          : step.locator === 'visual'
            ? {
                locator: 'visual',
                template_id: step.visualTemplateId,
                ...(step.visualThreshold !== null ? { threshold: Number(step.visualThreshold) } : {}),
                anchor_x_ratio: Number(step.visualAnchorXRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO),
                anchor_y_ratio: Number(step.visualAnchorYRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO)
              }
          : {
              selector: step.selector.trim()
            }),
        text: step.text,
        input_mode: step.inputMode,
        ...(step.inputMode === 'otp' && step.otpLength !== null
          ? { otp_length: Number(step.otpLength) }
          : {}),
        ...(step.inputMode !== 'fill' && step.perCharDelayMs !== null
          ? { per_char_delay_ms: Number(step.perCharDelayMs) }
          : {})
      }
    case 'select_option':
      return {
        field_target: buildOcrTargetPayload(step.fieldTarget),
        option_target: buildOcrTargetPayload(step.optionTarget),
        verify_selected: step.verifySelected
      }
    case 'template_assert':
      return step.threshold === null
        ? {}
        : {
            threshold: Number(step.threshold)
          }
    case 'ocr_assert':
      return {
        scope: step.ocrAssertionScope,
        assertion: step.ocrAssertionMode,
        ocr_target: buildOcrTargetPayload(
          step.ocrTarget,
          step.ocrAssertionScope === 'page' ? 'page' : 'viewport'
        ),
        ...(step.ocrAssertionScope === 'element_legacy'
          ? { selector: step.selector.trim() }
          : {}),
        ...(step.ocrAssertionMode === 'count' && step.ocrExpectedCount !== null
          ? { expected_count: Number(step.ocrExpectedCount) }
          : {})
      }
    case 'component_call':
      return {}
    case 'conditional_branch':
      return {
        branches: step.conditionalBranches.map((branch) => {
          const condition =
            branch.conditionType === 'ocr_text_visible'
              ? {
                  type: 'ocr_text_visible',
                  ocr_target: buildOcrTargetPayload(branch.ocrTarget)
                }
              : branch.conditionType === 'template_visible'
                ? {
                    type: 'template_visible',
                    template_id: branch.templateId,
                    ...(branch.threshold !== null ? { threshold: Number(branch.threshold) } : {})
                  }
                : {
                    type: 'selector_exists',
                    selector: branch.selector.trim()
                  }

          return {
            branch_key: branch.branchKey.trim(),
            branch_name: branch.branchName.trim(),
            condition,
            steps: branch.steps.map((childStep, childIndex) => buildNestedStepWritePayload(childStep, childIndex))
          }
        }),
        ...(step.elseBranchEnabled
          ? {
              else_branch: {
                enabled: true,
                branch_name: step.elseBranchName.trim() || '默认分支',
                steps: step.elseSteps.map((childStep, childIndex) => buildNestedStepWritePayload(childStep, childIndex))
              }
            }
          : {})
      }
    case 'navigate':
      return {
        url: step.url.trim(),
        wait_until: step.waitUntil
      }
    case 'scroll': {
      const payload: Record<string, unknown> = {
        target: step.scrollTarget,
        direction: step.direction,
        distance: Number(step.distance ?? DEFAULT_SCROLL_DISTANCE),
        behavior: step.behavior
      }

      if (step.scrollTarget === 'element') {
        if (step.locator === 'ocr') {
          payload.locator = 'ocr'
          payload.ocr_target = buildOcrTargetPayload(step.ocrTarget)
        } else if (step.locator === 'visual') {
          payload.locator = 'visual'
          payload.template_id = step.visualTemplateId
          if (step.visualThreshold !== null) {
            payload.threshold = Number(step.visualThreshold)
          }
          payload.anchor_x_ratio = Number(step.visualAnchorXRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO)
          payload.anchor_y_ratio = Number(step.visualAnchorYRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO)
        } else {
          payload.selector = step.selector.trim()
        }
      }

      return payload
    }
    case 'long_press':
      return step.locator === 'ocr'
        ? {
            locator: 'ocr',
            ocr_target: buildOcrTargetPayload(step.ocrTarget),
            duration_ms: Number(step.durationMs ?? DEFAULT_LONG_PRESS_DURATION_MS),
            button: step.button
          }
        : step.locator === 'visual'
          ? {
              locator: 'visual',
              template_id: step.visualTemplateId,
              ...(step.visualThreshold !== null ? { threshold: Number(step.visualThreshold) } : {}),
              anchor_x_ratio: Number(step.visualAnchorXRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO),
              anchor_y_ratio: Number(step.visualAnchorYRatio ?? DEFAULT_VISUAL_ANCHOR_RATIO),
              duration_ms: Number(step.durationMs ?? DEFAULT_LONG_PRESS_DURATION_MS),
              button: step.button
            }
        : {
            selector: step.selector.trim(),
            duration_ms: Number(step.durationMs ?? DEFAULT_LONG_PRESS_DURATION_MS),
            button: step.button
          }
  }
}

function buildAdditionalPayload(step: StepDraft): Record<string, unknown> {
  const extraPayload = parseExtraPayloadJson(step)
  const value = 'value' in extraPayload ? extraPayload.value : undefined
  if (!value) {
    return {}
  }
  return Object.fromEntries(
    Object.entries(value).filter(
      ([key]: [string, unknown]): boolean => !STRUCTURED_PAYLOAD_KEYS.has(key)
    )
  )
}

export function buildStepWritePayload(step: StepDraft, index: number): StepWritePayload {
  const additionalPayload = buildAdditionalPayload(step)

  return {
    stepNo: index + 1,
    type: step.type,
    name: step.name.trim() || `${STEP_TYPE_LABELS[step.type]} ${index + 1}`,
    templateId: step.type === 'template_assert' || step.type === 'ocr_assert' ? step.templateId : null,
    componentId: step.type === 'component_call' ? step.componentId : null,
    payloadJson: {
      ...additionalPayload,
      ...buildStructuredPayload(step)
    },
    timeoutMs: Number(step.timeoutMs),
    retryTimes: Number(step.retryTimes)
  }
}

function buildNestedStepWritePayload(step: StepDraft, index: number): Record<string, unknown> {
  const additionalPayload = buildAdditionalPayload(step)

  return {
    step_type: step.type,
    step_name: step.name.trim() || `${STEP_TYPE_LABELS[step.type]} ${index + 1}`,
    template_id: step.type === 'template_assert' || step.type === 'ocr_assert' ? step.templateId : null,
    component_id: null,
    payload_json: {
      ...additionalPayload,
      ...buildStructuredPayload(step)
    },
    timeout_ms: Number(step.timeoutMs),
    retry_times: Number(step.retryTimes)
  }
}

export function formatStepSummary(source: StepSummarySource) {
  const payload = source.payloadJson ?? {}
  const timeoutAndRetry = buildTimeoutAndRetry(source.timeoutMs, source.retryTimes)

  switch (source.type) {
    case 'wait': {
      const waitMs =
        typeof payload.ms === 'number' && Number.isFinite(payload.ms) ? payload.ms : '--'
      return {
        target: `等待 ${waitMs} ms`,
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['ms'])}`
      }
    }
    case 'click':
      {
        const locatorSummary = buildLocatorSummary(payload)
        const knownKeys =
          locatorSummary.locator === 'ocr'
            ? ['locator', 'ocr_target', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence']
            : locatorSummary.locator === 'visual'
              ? ['locator', 'template_id', 'threshold', 'anchor_x_ratio', 'anchor_y_ratio']
            : ['selector']
      return {
        target: `点击 ${locatorSummary.target}`,
        note: `${locatorSummary.note} · ${timeoutAndRetry}${formatExtraPayloadKeys(payload, knownKeys)}`
      }
      }
    case 'input':
      {
        const locatorSummary = buildLocatorSummary(payload)
        const inputMode = isInputMode(payload.input_mode) ? payload.input_mode : DEFAULT_INPUT_MODE
        const modeLabelMap: Record<InputMode, string> = {
          fill: '普通输入',
          type: '键盘输入',
          otp: '验证码输入'
        }
        const knownKeys =
          locatorSummary.locator === 'ocr'
            ? ['locator', 'ocr_target', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'text', 'input_mode', 'otp_length', 'per_char_delay_ms']
            : locatorSummary.locator === 'visual'
              ? ['locator', 'template_id', 'threshold', 'anchor_x_ratio', 'anchor_y_ratio', 'text', 'input_mode', 'otp_length', 'per_char_delay_ms']
            : ['selector', 'text', 'input_mode', 'otp_length', 'per_char_delay_ms']
      return {
        target: `输入到 ${locatorSummary.target}`,
        note: `文本 ${formatTextValue(payload.text)} · ${modeLabelMap[inputMode]}${typeof payload.otp_length === 'number' ? `(${payload.otp_length}位)` : ''} · ${locatorSummary.note} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          knownKeys
        )}`
      }
      }
    case 'select_option': {
      const fieldTarget = parseOcrTargetPayload(payload.field_target)
      const optionTarget = parseOcrTargetPayload(payload.option_target)
      return {
        target: `OCR 选择 ${formatTextValue(fieldTarget.text)} → ${formatTextValue(optionTarget.text)}`,
        note: `${payload.verify_selected === false ? '不验证选中结果' : '验证选中结果'} · ${fieldTarget.language}/${optionTarget.language} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          ['field_target', 'option_target', 'verify_selected']
        )}`
      }
    }
    case 'template_assert': {
      const threshold =
        typeof payload.threshold === 'number' && Number.isFinite(payload.threshold)
          ? `阈值 ${payload.threshold.toFixed(2)}`
          : '使用模板默认阈值'
      return {
        target: source.templateId ? `模板 #${source.templateId}` : '未选择模板',
        note: `${threshold} · ${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['threshold'])}`
      }
    }
    case 'ocr_assert': {
      const scope = isOcrAssertionScope(payload.scope)
        ? payload.scope
        : typeof payload.selector === 'string' && payload.selector.trim()
          ? 'element_legacy'
          : 'viewport'
      const target = hasOwn(payload, 'ocr_target')
        ? parseOcrTargetPayload(payload.ocr_target)
        : parseOcrTargetPayload({
            text: payload.expected_text,
            match_mode: payload.match_mode,
            case_sensitive: payload.case_sensitive,
            scope: 'viewport'
          })
      const assertion = isOcrAssertionMode(payload.assertion)
        ? payload.assertion
        : 'present'
      const scopeLabel =
        scope === 'element_legacy'
          ? `兼容元素区域 ${formatTextValue(payload.selector)}`
          : scope === 'page'
            ? '整页'
            : '当前视口'
      return {
        target: `OCR ${assertion} ${formatTextValue(target.text)}`,
        note: `${scopeLabel} · ${target.matchMode} · ${target.language} · ${target.role}${assertion === 'count' ? ` · 期望数量 ${String(payload.expected_count ?? '--')}` : ''} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          ['scope', 'assertion', 'ocr_target', 'selector', 'expected_count', 'expected_text', 'match_mode', 'case_sensitive']
        )}`
      }
    }
    case 'component_call':
      return {
        target: source.componentId ? `组件 #${source.componentId}` : '未选择组件',
        note: timeoutAndRetry
      }
    case 'conditional_branch': {
      const branches = Array.isArray(payload.branches) ? payload.branches : []
      const elseBranch = isRecord(payload.else_branch) ? payload.else_branch : null
      const enabledElse = elseBranch?.enabled === true
      return {
        target: `条件分支 · ${branches.length} 个条件${enabledElse ? ' + 默认分支' : ''}`,
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['branches', 'else_branch'])}`
      }
    }
    case 'navigate': {
      const waitUntil = isNavigateWaitUntil(payload.wait_until) ? payload.wait_until : 'load'
      return {
        target: `访问 ${formatTextValue(payload.url)}（等待 ${waitUntil}）`,
        note: `${timeoutAndRetry}${formatExtraPayloadKeys(payload, ['url', 'wait_until'])}`
      }
    }
    case 'scroll': {
      const target = isScrollTarget(payload.target) ? payload.target : 'page'
      const direction = isScrollDirection(payload.direction) ? payload.direction : 'down'
      const distance =
        typeof payload.distance === 'number' && Number.isFinite(payload.distance)
          ? payload.distance
          : '--'
      const directionLabelMap: Record<ScrollDirection, string> = {
        up: '向上',
        down: '向下',
        left: '向左',
        right: '向右'
      }
      const locatorSummary = target === 'element' ? buildLocatorSummary(payload) : null
      const summaryPrefix = target === 'element' ? `元素 ${locatorSummary?.target ?? '--'}` : '页面'
      const locatorNote = target === 'element' ? `${locatorSummary?.note ?? ''} · ` : ''
      const knownKeys =
        target === 'element'
          ? (locatorSummary?.locator === 'ocr'
              ? ['target', 'locator', 'ocr_target', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'direction', 'distance', 'behavior']
              : locatorSummary?.locator === 'visual'
                ? ['target', 'locator', 'template_id', 'threshold', 'anchor_x_ratio', 'anchor_y_ratio', 'direction', 'distance', 'behavior']
              : ['target', 'selector', 'direction', 'distance', 'behavior'])
          : ['target', 'direction', 'distance', 'behavior']

      return {
        target: `${summaryPrefix}${directionLabelMap[direction]}滑动 ${distance} px`,
        note: `${locatorNote}行为 ${isScrollBehavior(payload.behavior) ? payload.behavior : 'auto'} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          knownKeys
        )}`
      }
    }
    case 'long_press': {
      const locatorSummary = buildLocatorSummary(payload)
      const duration =
        typeof payload.duration_ms === 'number' && Number.isFinite(payload.duration_ms)
          ? payload.duration_ms
          : DEFAULT_LONG_PRESS_DURATION_MS
        const knownKeys =
          locatorSummary.locator === 'ocr'
            ? ['locator', 'ocr_target', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'duration_ms', 'button']
          : locatorSummary.locator === 'visual'
            ? ['locator', 'template_id', 'threshold', 'anchor_x_ratio', 'anchor_y_ratio', 'duration_ms', 'button']
            : ['selector', 'duration_ms', 'button']
      return {
        target: `长按 ${locatorSummary.target} ${duration} ms`,
        note: `${locatorSummary.note} · 按钮 ${isLongPressButton(payload.button) ? payload.button : 'left'} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          knownKeys
        )}`
      }
    }
  }
}

export function formatStepSummaryFromStep(step: Step) {
  return formatStepSummary({
    type: step.type,
    payloadJson: step.payloadJson,
    templateId: step.templateId,
    componentId: step.componentId,
    timeoutMs: step.timeoutMs,
    retryTimes: step.retryTimes
  })
}
