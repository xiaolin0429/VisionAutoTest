import type {
  InputMode,
  LocatorType,
  LongPressButton,
  NavigateWaitUntil,
  OcrAssertMatchMode,
  OcrLocatorMatchMode,
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
  expectedText: string
  matchMode: OcrAssertMatchMode
  caseSensitive: boolean
  url: string
  waitUntil: NavigateWaitUntil
  scrollTarget: ScrollTargetType
  direction: ScrollDirection
  distance: number | null
  behavior: ScrollBehaviorMode
  durationMs: number | null
  button: LongPressButton
  locator: LocatorType
  ocrText: string
  ocrMatchMode: OcrLocatorMatchMode
  ocrCaseSensitive: boolean
  ocrOccurrence: number
  extraPayloadJson: string
  timeoutMs: number
  retryTimes: number
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
  expectedText?: string
  matchMode?: string
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
  ocrText?: string
  ocrMatchMode?: string
  ocrOccurrence?: string
}

export interface StepTypeOption {
  label: string
  value: StepType
}

export const STEP_TYPE_LABELS: Record<StepType, string> = {
  wait: '等待',
  click: '点击',
  input: '输入',
  template_assert: '模板断言',
  ocr_assert: 'OCR 断言',
  component_call: '组件调用',
  navigate: '访问页面',
  scroll: '滑动',
  long_press: '长按'
}

export const OCR_MATCH_MODE_OPTIONS: Array<{ label: string; value: OcrAssertMatchMode }> = [
  { label: '包含', value: 'contains' },
  { label: '完全匹配', value: 'exact' }
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
  { label: '包含', value: 'contains' },
  { label: '完全匹配', value: 'exact' }
]

export const INPUT_MODE_OPTIONS: Array<{ label: string; value: InputMode }> = [
  { label: '普通输入', value: 'fill' },
  { label: '键盘输入', value: 'type' },
  { label: '验证码输入', value: 'otp' }
]

const DEFAULT_WAIT_MS = 200
const DEFAULT_TIMEOUT_MS = 15000
const DEFAULT_SCROLL_DISTANCE = 1200
const DEFAULT_LONG_PRESS_DURATION_MS = 800
const DEFAULT_INPUT_MODE: InputMode = 'fill'
const DEFAULT_OTP_PER_CHAR_DELAY_MS = 80
const DEFAULT_VISUAL_ANCHOR_RATIO = 0.5

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isNavigateWaitUntil(value: unknown): value is NavigateWaitUntil {
  return value === 'load' || value === 'domcontentloaded' || value === 'networkidle'
}

function isSupportedNavigateUrl(value: string) {
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
  return value === 'exact' || value === 'contains'
}

function isInputMode(value: unknown): value is InputMode {
  return value === 'fill' || value === 'type' || value === 'otp'
}

function stringifyPayload(payload: Record<string, unknown>) {
  const keys = Object.keys(payload)
  if (keys.length === 0) {
    return '{}'
  }

  return JSON.stringify(payload, null, 2)
}

function formatTextValue(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) {
    return '--'
  }

  return value.trim()
}

function buildLocatorSummary(payload: Record<string, unknown>) {
  const locator = isLocatorType(payload.locator) ? payload.locator : 'selector'
  if (locator === 'ocr') {
    const matchMode = isOcrLocatorMatchMode(payload.ocr_match_mode)
      ? payload.ocr_match_mode
      : 'contains'
    const caseSensitive = payload.ocr_case_sensitive === true ? '区分大小写' : '忽略大小写'
    const occurrence =
      typeof payload.ocr_occurrence === 'number' && Number.isFinite(payload.ocr_occurrence)
        ? payload.ocr_occurrence
        : 1

    return {
      locator,
      target: `OCR ${formatTextValue(payload.ocr_text)}`,
      note: `${matchMode} · ${caseSensitive} · 第 ${occurrence} 个匹配`
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
  const values: StepType[] = [
    'wait',
    'click',
    'input',
    'template_assert',
    'ocr_assert',
    'navigate',
    'scroll',
    'long_press'
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
    expectedText: '',
    matchMode: 'contains',
    caseSensitive: false,
    url: '',
    waitUntil: 'load',
    scrollTarget: 'page',
    direction: 'down',
    distance: DEFAULT_SCROLL_DISTANCE,
    behavior: 'auto',
    durationMs: DEFAULT_LONG_PRESS_DURATION_MS,
    button: 'left',
    locator: 'selector',
    ocrText: '',
    ocrMatchMode: 'contains',
    ocrCaseSensitive: false,
    ocrOccurrence: 1,
    extraPayloadJson: '{}',
    timeoutMs: DEFAULT_TIMEOUT_MS,
    retryTimes: 0
  }
}

export function normalizeStepDrafts(items: StepDraft[]) {
  return items.map((item, index) => ({
    ...item,
    stepNo: index + 1
  }))
}

export function parseExtraPayloadJson(step: Pick<StepDraft, 'extraPayloadJson'>) {
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

export function supportsOcrLocator(type: StepType): boolean {
  return type === 'click' || type === 'input' || type === 'scroll' || type === 'long_press'
}

export function normalizeStepByType(step: StepDraft, nextType: StepType): StepDraft {
  const keepLocator = supportsOcrLocator(nextType)
  return {
    ...step,
    type: nextType,
    templateId: nextType === 'template_assert' || nextType === 'ocr_assert' ? step.templateId : null,
    componentId: nextType === 'component_call' ? step.componentId : null,
    waitMs: nextType === 'wait' ? step.waitMs ?? DEFAULT_WAIT_MS : null,
    selector:
      nextType === 'click' ||
      nextType === 'input' ||
      nextType === 'ocr_assert' ||
      nextType === 'scroll' ||
      nextType === 'long_press'
        ? step.selector
        : '',
    visualTemplateId:
      nextType === 'click' || nextType === 'input' || nextType === 'scroll' || nextType === 'long_press'
        ? step.visualTemplateId
        : null,
    visualThreshold:
      nextType === 'click' || nextType === 'input' || nextType === 'scroll' || nextType === 'long_press'
        ? step.visualThreshold
        : null,
    visualAnchorXRatio:
      nextType === 'click' || nextType === 'input' || nextType === 'scroll' || nextType === 'long_press'
        ? step.visualAnchorXRatio
        : DEFAULT_VISUAL_ANCHOR_RATIO,
    visualAnchorYRatio:
      nextType === 'click' || nextType === 'input' || nextType === 'scroll' || nextType === 'long_press'
        ? step.visualAnchorYRatio
        : DEFAULT_VISUAL_ANCHOR_RATIO,
    text: nextType === 'input' ? step.text : '',
    inputMode: nextType === 'input' ? step.inputMode : DEFAULT_INPUT_MODE,
    otpLength: nextType === 'input' ? step.otpLength : null,
    perCharDelayMs: nextType === 'input' ? step.perCharDelayMs : DEFAULT_OTP_PER_CHAR_DELAY_MS,
    threshold: nextType === 'template_assert' ? step.threshold : null,
    expectedText: nextType === 'ocr_assert' ? step.expectedText : '',
    matchMode: nextType === 'ocr_assert' ? step.matchMode : 'contains',
    caseSensitive: nextType === 'ocr_assert' ? step.caseSensitive : false,
    url: nextType === 'navigate' ? step.url : '',
    waitUntil: nextType === 'navigate' ? step.waitUntil : 'load',
    scrollTarget: nextType === 'scroll' ? step.scrollTarget : 'page',
    direction: nextType === 'scroll' ? step.direction : 'down',
    distance: nextType === 'scroll' ? step.distance ?? DEFAULT_SCROLL_DISTANCE : null,
    behavior: nextType === 'scroll' ? step.behavior : 'auto',
    durationMs: nextType === 'long_press' ? step.durationMs ?? DEFAULT_LONG_PRESS_DURATION_MS : null,
    button: nextType === 'long_press' ? step.button : 'left',
    locator: keepLocator ? step.locator : 'selector',
    ocrText: keepLocator ? step.ocrText : '',
    ocrMatchMode: keepLocator ? step.ocrMatchMode : 'contains',
    ocrCaseSensitive: keepLocator ? step.ocrCaseSensitive : false,
    ocrOccurrence: keepLocator ? step.ocrOccurrence : 1
  }
}

export function buildStepDraft(step: Step): StepDraft {
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
      draft.ocrText = typeof payload.ocr_text === 'string' ? payload.ocr_text : ''
      draft.ocrMatchMode = isOcrLocatorMatchMode(payload.ocr_match_mode) ? payload.ocr_match_mode : 'contains'
      draft.ocrCaseSensitive = payload.ocr_case_sensitive === true
      draft.ocrOccurrence = typeof payload.ocr_occurrence === 'number' && payload.ocr_occurrence >= 1 ? payload.ocr_occurrence : 1
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      delete payload.ocr_text
      delete payload.ocr_match_mode
      delete payload.ocr_case_sensitive
      delete payload.ocr_occurrence
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
      draft.ocrText = typeof payload.ocr_text === 'string' ? payload.ocr_text : ''
      draft.ocrMatchMode = isOcrLocatorMatchMode(payload.ocr_match_mode) ? payload.ocr_match_mode : 'contains'
      draft.ocrCaseSensitive = payload.ocr_case_sensitive === true
      draft.ocrOccurrence = typeof payload.ocr_occurrence === 'number' && payload.ocr_occurrence >= 1 ? payload.ocr_occurrence : 1
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
      delete payload.ocr_text
      delete payload.ocr_match_mode
      delete payload.ocr_case_sensitive
      delete payload.ocr_occurrence
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
      draft.expectedText = typeof payload.expected_text === 'string' ? payload.expected_text : ''
      draft.matchMode = payload.match_mode === 'exact' ? 'exact' : 'contains'
      draft.caseSensitive = payload.case_sensitive === true
      delete payload.selector
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
      draft.ocrText = typeof payload.ocr_text === 'string' ? payload.ocr_text : ''
      draft.ocrMatchMode = isOcrLocatorMatchMode(payload.ocr_match_mode) ? payload.ocr_match_mode : 'contains'
      draft.ocrCaseSensitive = payload.ocr_case_sensitive === true
      draft.ocrOccurrence = typeof payload.ocr_occurrence === 'number' && payload.ocr_occurrence >= 1 ? payload.ocr_occurrence : 1
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
      delete payload.ocr_text
      delete payload.ocr_match_mode
      delete payload.ocr_case_sensitive
      delete payload.ocr_occurrence
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
      draft.ocrText = typeof payload.ocr_text === 'string' ? payload.ocr_text : ''
      draft.ocrMatchMode = isOcrLocatorMatchMode(payload.ocr_match_mode) ? payload.ocr_match_mode : 'contains'
      draft.ocrCaseSensitive = payload.ocr_case_sensitive === true
      draft.ocrOccurrence = typeof payload.ocr_occurrence === 'number' && payload.ocr_occurrence >= 1 ? payload.ocr_occurrence : 1
      delete payload.locator
      delete payload.selector
      delete payload.template_id
      delete payload.threshold
      delete payload.anchor_x_ratio
      delete payload.anchor_y_ratio
      delete payload.duration_ms
      delete payload.button
      delete payload.ocr_text
      delete payload.ocr_match_mode
      delete payload.ocr_case_sensitive
      delete payload.ocr_occurrence
      break
    case 'component_call':
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
        if (!step.ocrText.trim()) {
          errors.ocrText = '点击步骤使用 OCR 定位时必须填写识别文本。'
        }
        if (!isOcrLocatorMatchMode(step.ocrMatchMode)) {
          errors.ocrMatchMode = 'OCR 匹配模式仅支持 exact 或 contains。'
        }
        if (!Number.isInteger(step.ocrOccurrence) || step.ocrOccurrence < 1) {
          errors.ocrOccurrence = 'OCR 匹配序号必须为大于等于 1 的整数。'
        }
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
        if (!step.ocrText.trim()) {
          errors.ocrText = '输入步骤使用 OCR 定位时必须填写识别文本。'
        }
        if (!isOcrLocatorMatchMode(step.ocrMatchMode)) {
          errors.ocrMatchMode = 'OCR 匹配模式仅支持 exact 或 contains。'
        }
        if (!Number.isInteger(step.ocrOccurrence) || step.ocrOccurrence < 1) {
          errors.ocrOccurrence = 'OCR 匹配序号必须为大于等于 1 的整数。'
        }
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
      if (!step.selector.trim()) {
        errors.selector = 'OCR 断言必须填写选择器。'
      }
      if (!step.expectedText.trim()) {
        errors.expectedText = 'OCR 断言必须填写期望文本。'
      }
      if (step.matchMode !== 'exact' && step.matchMode !== 'contains') {
        errors.matchMode = '匹配模式仅支持 exact 或 contains。'
      }
      break
    case 'component_call':
      if (step.componentId === null) {
        errors.componentId = '组件调用必须选择组件。'
      }
      break
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
          if (!step.ocrText.trim()) {
            errors.ocrText = '元素滑动使用 OCR 定位时必须填写识别文本。'
          }
          if (!isOcrLocatorMatchMode(step.ocrMatchMode)) {
            errors.ocrMatchMode = 'OCR 匹配模式仅支持 exact 或 contains。'
          }
          if (!Number.isInteger(step.ocrOccurrence) || step.ocrOccurrence < 1) {
            errors.ocrOccurrence = 'OCR 匹配序号必须为大于等于 1 的整数。'
          }
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
        if (!step.ocrText.trim()) {
          errors.ocrText = '长按步骤使用 OCR 定位时必须填写识别文本。'
        }
        if (!isOcrLocatorMatchMode(step.ocrMatchMode)) {
          errors.ocrMatchMode = 'OCR 匹配模式仅支持 exact 或 contains。'
        }
        if (!Number.isInteger(step.ocrOccurrence) || step.ocrOccurrence < 1) {
          errors.ocrOccurrence = 'OCR 匹配序号必须为大于等于 1 的整数。'
        }
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

function buildStructuredPayload(step: StepDraft) {
  switch (step.type) {
    case 'wait':
      return {
        ms: Number(step.waitMs ?? 0)
      }
    case 'click':
      return step.locator === 'ocr'
        ? {
            locator: 'ocr',
            ocr_text: step.ocrText.trim(),
            ocr_match_mode: step.ocrMatchMode,
            ocr_case_sensitive: step.ocrCaseSensitive,
            ocr_occurrence: Number(step.ocrOccurrence)
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
              ocr_text: step.ocrText.trim(),
              ocr_match_mode: step.ocrMatchMode,
              ocr_case_sensitive: step.ocrCaseSensitive,
              ocr_occurrence: Number(step.ocrOccurrence)
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
    case 'template_assert':
      return step.threshold === null
        ? {}
        : {
            threshold: Number(step.threshold)
          }
    case 'ocr_assert':
      return {
        selector: step.selector.trim(),
        expected_text: step.expectedText,
        match_mode: step.matchMode,
        case_sensitive: step.caseSensitive
      }
    case 'component_call':
      return {}
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
          payload.ocr_text = step.ocrText.trim()
          payload.ocr_match_mode = step.ocrMatchMode
          payload.ocr_case_sensitive = step.ocrCaseSensitive
          payload.ocr_occurrence = Number(step.ocrOccurrence)
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
            ocr_text: step.ocrText.trim(),
            ocr_match_mode: step.ocrMatchMode,
            ocr_case_sensitive: step.ocrCaseSensitive,
            ocr_occurrence: Number(step.ocrOccurrence),
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

export function buildStepWritePayload(step: StepDraft, index: number): StepWritePayload {
  const extraPayload = parseExtraPayloadJson(step)
  const additionalPayload = 'value' in extraPayload ? extraPayload.value : {}

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
            ? ['locator', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence']
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
            ? ['locator', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'text', 'input_mode', 'otp_length', 'per_char_delay_ms']
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
      const matchMode = payload.match_mode === 'exact' ? 'exact' : 'contains'
      const caseSensitive = payload.case_sensitive === true ? '区分大小写' : '忽略大小写'
      return {
        target: `OCR ${formatTextValue(payload.selector)}`,
        note: `期望文本 ${formatTextValue(payload.expected_text)} · ${matchMode} · ${caseSensitive} · ${timeoutAndRetry}${formatExtraPayloadKeys(
          payload,
          ['selector', 'expected_text', 'match_mode', 'case_sensitive']
        )}`
      }
    }
    case 'component_call':
      return {
        target: source.componentId ? `组件 #${source.componentId}` : '未选择组件',
        note: timeoutAndRetry
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
              ? ['target', 'locator', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'direction', 'distance', 'behavior']
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
            ? ['locator', 'ocr_text', 'ocr_match_mode', 'ocr_case_sensitive', 'ocr_occurrence', 'duration_ms', 'button']
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
