import { describe, expect, it } from 'vitest'

import type { Step, StepType, StepWritePayload } from '@/types/models'
import {
  buildStepDraft,
  buildStepWritePayload,
  createBranchChildStepDraft,
  createEmptyStepDraft,
  createOcrTargetDraft,
  formatStepSummary,
  normalizeStepByType,
  validateStepDraft,
  type ConditionalBranchDraft,
  type StepDraft
} from '@/utils/steps'

function createDraft(
  index: number,
  type: StepType,
  name: string
): StepDraft {
  const draft = normalizeStepByType(createEmptyStepDraft(index), type)
  draft.id = index + 1
  draft.stepNo = 100 + index
  draft.name = name
  draft.timeoutMs = 7_000 + index
  draft.retryTimes = index % 3
  draft.extraPayloadJson = JSON.stringify({
    trace_label: `trace-${type}`,
    timeout_ms: 'advanced-value-must-not-replace-runtime-field'
  })
  return draft
}

function createChild(
  index: number,
  type: StepType,
  name: string
): StepDraft {
  const child = normalizeStepByType(createBranchChildStepDraft(index), type)
  child.id = 100 + index
  child.name = name
  child.extraPayloadJson = JSON.stringify({
    child_extension: `${type}-${index}`
  })
  return child
}

function createBranch(
  index: number,
  overrides: Partial<ConditionalBranchDraft>
): ConditionalBranchDraft {
  return {
    id: 200 + index,
    branchKey: `branch_${index + 1}`,
    branchName: `分支 ${index + 1}`,
    conditionType: 'selector_exists',
    ocrTarget: createOcrTargetDraft(),
    templateId: null,
    threshold: null,
    selector: '#ready',
    steps: [createChild(index, 'wait', `分支等待 ${index + 1}`)],
    ...overrides
  }
}

function createAllStepDrafts(): StepDraft[] {
  const wait = createDraft(0, 'wait', '等待稳定')
  wait.waitMs = 350

  const click = createDraft(1, 'click', '视觉点击')
  click.locator = 'visual'
  click.visualTemplateId = 101
  click.visualThreshold = 0.87
  click.visualAnchorXRatio = 0.4
  click.visualAnchorYRatio = 0.65
  click.extraPayloadJson = JSON.stringify({
    trace_label: 'trace-click',
    template_id: 999,
    anchor_x_ratio: 0
  })

  const input = createDraft(2, 'input', 'OCR 验证码输入')
  input.locator = 'ocr'
  input.ocrTarget = createOcrTargetDraft({
    text: '验证码',
    matchMode: 'exact',
    caseSensitive: true,
    occurrence: 2,
    scope: 'page',
    language: 'zh_en',
    role: 'input',
    actionPoint: 'associated_control'
  })
  input.text = '123456'
  input.inputMode = 'otp'
  input.otpLength = 6
  input.perCharDelayMs = 90

  const templateAssert = createDraft(3, 'template_assert', '模板断言')
  templateAssert.templateId = 101
  templateAssert.threshold = 0.91

  const ocrAssert = createDraft(4, 'ocr_assert', 'OCR 断言')
  ocrAssert.ocrAssertionScope = 'page'
  ocrAssert.ocrAssertionMode = 'present'
  ocrAssert.ocrTarget = createOcrTargetDraft({
    text: '欢迎回来',
    matchMode: 'contains',
    scope: 'page',
    role: 'text'
  })

  const componentCall = createDraft(5, 'component_call', '调用登录组件')
  componentCall.componentId = 42

  const navigate = createDraft(6, 'navigate', '打开页面')
  navigate.url = 'https://example.test/login'
  navigate.waitUntil = 'networkidle'

  const scroll = createDraft(7, 'scroll', '元素滑动')
  scroll.scrollTarget = 'element'
  scroll.locator = 'selector'
  scroll.selector = '[data-testid="results"]'
  scroll.direction = 'down'
  scroll.distance = 640
  scroll.behavior = 'smooth'

  const longPress = createDraft(8, 'long_press', 'OCR 长按')
  longPress.locator = 'ocr'
  longPress.ocrTarget = createOcrTargetDraft({
    text: '确认',
    matchMode: 'contains',
    role: 'button'
  })
  longPress.durationMs = 1_200
  longPress.button = 'left'

  const conditional = createDraft(9, 'conditional_branch', '多条件分支')
  const selectorChild = createChild(0, 'click', '点击工作台')
  selectorChild.selector = '#dashboard'
  const ocrChild = createChild(0, 'ocr_assert', '确认欢迎文案')
  ocrChild.ocrTarget.text = '欢迎回来'
  const templateChild = createChild(0, 'template_assert', '确认登录按钮')
  templateChild.templateId = 101
  templateChild.threshold = 0.88
  conditional.conditionalBranches = [
    createBranch(0, {
      branchKey: 'selector_ready',
      branchName: '选择器就绪',
      conditionType: 'selector_exists',
      selector: '#dashboard',
      steps: [selectorChild]
    }),
    createBranch(1, {
      branchKey: 'ocr_ready',
      branchName: 'OCR 就绪',
      conditionType: 'ocr_text_visible',
      ocrTarget: createOcrTargetDraft({
        text: '欢迎回来',
        matchMode: 'exact',
        caseSensitive: true
      }),
      steps: [ocrChild]
    }),
    createBranch(2, {
      branchKey: 'template_ready',
      branchName: '模板就绪',
      conditionType: 'template_visible',
      templateId: 101,
      threshold: 0.84,
      steps: [templateChild]
    })
  ]
  conditional.elseBranchEnabled = true
  conditional.elseBranchName = '默认处理'
  conditional.elseSteps = [createChild(0, 'wait', '默认等待')]
  conditional.extraPayloadJson = JSON.stringify({
    trace_label: 'trace-conditional',
    branches: 'advanced-value-must-not-replace-structured-branches'
  })

  const selectOption = createDraft(10, 'select_option', '选择国家')
  selectOption.fieldTarget = createOcrTargetDraft({
    text: '国家/地区',
    role: 'input',
    actionPoint: 'associated_control'
  })
  selectOption.optionTarget = createOcrTargetDraft({
    text: '中国',
    role: 'menu_item'
  })
  selectOption.verifySelected = true

  return [
    wait,
    click,
    input,
    templateAssert,
    ocrAssert,
    componentCall,
    navigate,
    scroll,
    longPress,
    conditional,
    selectOption
  ]
}

function toPersistedStep(payload: StepWritePayload, id: number): Step {
  return {
    id,
    stepNo: payload.stepNo,
    name: payload.name,
    type: payload.type,
    templateId: payload.templateId,
    componentId: payload.componentId,
    target: '',
    note: '',
    payloadJson: payload.payloadJson,
    timeoutMs: payload.timeoutMs,
    retryTimes: payload.retryTimes
  }
}

describe('all step type save regression', (): void => {
  it('serializes all ten original step types plus select_option', (): void => {
    const drafts = createAllStepDrafts()

    expect(drafts.map(validateStepDraft)).toEqual(
      Array.from({ length: 11 }, (): Record<string, string> => ({}))
    )

    const payloads = drafts.map(buildStepWritePayload)

    expect(payloads.map((payload: StepWritePayload): StepType => payload.type)).toEqual([
      'wait',
      'click',
      'input',
      'template_assert',
      'ocr_assert',
      'component_call',
      'navigate',
      'scroll',
      'long_press',
      'conditional_branch',
      'select_option'
    ])
    expect(payloads.map((payload: StepWritePayload): number => payload.stepNo)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
    ])
    expect(payloads[1].payloadJson).toMatchObject({
      trace_label: 'trace-click',
      locator: 'visual',
      template_id: 101,
      threshold: 0.87,
      anchor_x_ratio: 0.4,
      anchor_y_ratio: 0.65
    })
    expect(payloads[2].payloadJson).toMatchObject({
      locator: 'ocr',
      ocr_target: {
        text: '验证码',
        match_mode: 'exact',
        case_sensitive: true,
        occurrence: 2,
        scope: 'page',
        language: 'zh_en',
        role: 'input',
        action_point: 'associated_control'
      },
      text: '123456',
      input_mode: 'otp',
      otp_length: 6,
      per_char_delay_ms: 90
    })
    expect(payloads[3]).toMatchObject({
      templateId: 101,
      payloadJson: {
        trace_label: 'trace-template_assert',
        timeout_ms: 'advanced-value-must-not-replace-runtime-field',
        threshold: 0.91
      }
    })
    expect(payloads[4]).toMatchObject({
      templateId: null,
      payloadJson: expect.objectContaining({
        scope: 'page',
        assertion: 'present',
        ocr_target: expect.objectContaining({
          text: '欢迎回来',
          match_mode: 'contains',
          scope: 'page'
        })
      })
    })
    expect(payloads[5]).toMatchObject({
      componentId: 42,
      payloadJson: expect.objectContaining({
        trace_label: 'trace-component_call'
      })
    })
    expect(payloads[7].payloadJson).toMatchObject({
      target: 'element',
      selector: '[data-testid="results"]',
      direction: 'down',
      distance: 640,
      behavior: 'smooth'
    })
    expect(payloads[8].payloadJson).toMatchObject({
      locator: 'ocr',
      ocr_target: expect.objectContaining({
        text: '确认',
        role: 'button'
      }),
      duration_ms: 1_200,
      button: 'left'
    })

    const conditionalPayload = payloads[9].payloadJson
    expect(conditionalPayload.trace_label).toBe('trace-conditional')
    expect(conditionalPayload.branches).toEqual([
      expect.objectContaining({
        branch_key: 'selector_ready',
        condition: {
          type: 'selector_exists',
          selector: '#dashboard'
        }
      }),
      expect.objectContaining({
        branch_key: 'ocr_ready',
        condition: {
          type: 'ocr_text_visible',
          ocr_target: expect.objectContaining({
            text: '欢迎回来',
            match_mode: 'exact',
            case_sensitive: true
          })
        }
      }),
      expect.objectContaining({
        branch_key: 'template_ready',
        condition: {
          type: 'template_visible',
          template_id: 101,
          threshold: 0.84
        }
      })
    ])
    expect(conditionalPayload.else_branch).toEqual(
      expect.objectContaining({
        enabled: true,
        branch_name: '默认处理'
      })
    )
    expect(payloads[10].payloadJson).toMatchObject({
      field_target: expect.objectContaining({
        text: '国家/地区',
        role: 'input',
        action_point: 'associated_control'
      }),
      option_target: expect.objectContaining({
        text: '中国',
        role: 'menu_item'
      }),
      verify_selected: true
    })
  })

  it('round-trips persisted payloads without losing templates, locators, branches, or extensions', (): void => {
    const initialPayloads = createAllStepDrafts().map(buildStepWritePayload)
    const roundTrippedPayloads = initialPayloads.map(
      (payload: StepWritePayload, index: number): StepWritePayload =>
        buildStepWritePayload(
          buildStepDraft(toPersistedStep(payload, index + 1)),
          index
        )
    )

    expect(roundTrippedPayloads).toEqual(initialPayloads)
  })
})

describe('OCR payload compatibility', (): void => {
  it('creates selector-free viewport assertions and validates count and relation fields', (): void => {
    const draft = createDraft(0, 'ocr_assert', '新 OCR 断言')
    draft.ocrTarget.text = '提交成功'

    expect(draft.ocrAssertionScope).toBe('viewport')
    expect(validateStepDraft(draft)).not.toHaveProperty('selector')
    expect(buildStepWritePayload(draft, 0).payloadJson).toMatchObject({
      scope: 'viewport',
      assertion: 'present',
      ocr_target: expect.objectContaining({
        text: '提交成功',
        scope: 'viewport'
      })
    })
    expect(buildStepWritePayload(draft, 0).payloadJson).not.toHaveProperty('selector')

    draft.ocrAssertionMode = 'count'
    expect(validateStepDraft(draft).ocrExpectedCount).toBeTruthy()
    draft.ocrExpectedCount = 0
    expect(validateStepDraft(draft).ocrExpectedCount).toBeUndefined()

    draft.ocrAssertionMode = 'relation'
    expect(validateStepDraft(draft).ocrTarget).toBeTruthy()
    draft.ocrTarget.relation = {
      type: 'right_of',
      anchorText: '状态',
      maxDistanceRatio: 0.25
    }
    expect(validateStepDraft(draft).ocrTarget).toBeUndefined()
  })

  it('normalizes a legacy flat locator and saves only nested ocr_target', (): void => {
    const legacyStep: Step = {
      ...toPersistedStep(buildStepWritePayload(createDraft(0, 'click', '旧 OCR 点击'), 0), 1),
      payloadJson: {
        locator: 'ocr',
        ocr_text: ' 登录 ',
        ocr_match_mode: 'contains',
        ocr_case_sensitive: true,
        ocr_occurrence: 3,
        trace_label: 'legacy'
      }
    }

    const draft = buildStepDraft(legacyStep)
    const payload = buildStepWritePayload(draft, 0).payloadJson

    expect(draft.ocrTarget).toMatchObject({
      text: ' 登录 ',
      matchMode: 'contains',
      caseSensitive: true,
      occurrence: 3,
      scope: 'viewport'
    })
    expect(payload).toMatchObject({
      locator: 'ocr',
      trace_label: 'legacy',
      ocr_target: expect.objectContaining({
        text: '登录',
        match_mode: 'contains',
        occurrence: 3
      })
    })
    expect(payload).not.toHaveProperty('ocr_text')
    expect(payload).not.toHaveProperty('selector')
  })

  it('does not fall back to legacy fields when an invalid nested target is present', (): void => {
    const clickDraft = buildStepDraft({
      ...toPersistedStep(buildStepWritePayload(createDraft(0, 'click', '无效嵌套点击'), 0), 1),
      payloadJson: {
        locator: 'ocr',
        ocr_target: null,
        ocr_text: '不得回退'
      }
    })
    const assertionDraft = buildStepDraft({
      ...toPersistedStep(buildStepWritePayload(createDraft(1, 'ocr_assert', '无效嵌套断言'), 1), 2),
      payloadJson: {
        scope: 'viewport',
        ocr_target: null,
        expected_text: '不得回退'
      }
    })
    const branchDraft = buildStepDraft({
      ...toPersistedStep(buildStepWritePayload(createDraft(2, 'conditional_branch', '无效嵌套条件'), 2), 3),
      payloadJson: {
        branches: [
          {
            branch_key: 'invalid',
            branch_name: '无效目标',
            condition: {
              type: 'ocr_text_visible',
              ocr_target: null,
              expected_text: '不得回退'
            },
            steps: [
              {
                step_type: 'wait',
                step_name: '等待',
                payload_json: { ms: 1 }
              }
            ]
          }
        ]
      }
    })

    expect(clickDraft.ocrTarget.text).toBe('')
    expect(assertionDraft.ocrTarget.text).toBe('')
    expect(branchDraft.conditionalBranches[0].ocrTarget.text).toBe('')
    expect(validateStepDraft(clickDraft).ocrTarget).toBeTruthy()
    expect(validateStepDraft(assertionDraft).ocrTarget).toBeTruthy()
    expect(validateStepDraft(branchDraft).extraPayloadJson).toBeTruthy()
  })

  it('keeps legacy selector assertions in explicit compatibility mode', (): void => {
    const legacyStep: Step = {
      ...toPersistedStep(buildStepWritePayload(createDraft(0, 'ocr_assert', '旧 OCR 断言'), 0), 1),
      templateId: 102,
      payloadJson: {
        selector: '#result',
        expected_text: '提交成功',
        match_mode: 'contains',
        case_sensitive: false
      }
    }

    const draft = buildStepDraft(legacyStep)
    const payload = buildStepWritePayload(draft, 0).payloadJson
    const summary = formatStepSummary({
      type: 'ocr_assert',
      payloadJson: payload,
      templateId: 102,
      componentId: null,
      timeoutMs: 15_000,
      retryTimes: 0
    })

    expect(draft.ocrAssertionScope).toBe('element_legacy')
    expect(draft.ocrTarget.text).toBe('提交成功')
    expect(payload).toMatchObject({
      scope: 'element_legacy',
      selector: '#result',
      ocr_target: expect.objectContaining({
        text: '提交成功',
        scope: 'viewport'
      })
    })
    expect(payload).not.toHaveProperty('expected_text')
    expect(summary.note).toContain('兼容元素区域')
  })

  it('prevents advanced payload from overriding or adding fallback locator fields', (): void => {
    const draft = createDraft(0, 'click', '纯 OCR 点击')
    draft.locator = 'ocr'
    draft.ocrTarget = createOcrTargetDraft({ text: '提交' })
    draft.extraPayloadJson = JSON.stringify({
      ocr_target: { text: '错误覆盖' },
      ocr_text: '旧字段',
      selector: '#fallback',
      template_id: 99,
      extension_flag: true
    })

    const payload = buildStepWritePayload(draft, 0).payloadJson

    expect(payload).toEqual({
      extension_flag: true,
      locator: 'ocr',
      ocr_target: expect.objectContaining({ text: '提交' })
    })
  })

  it('clears locator, template and OCR state when switching step types', (): void => {
    const input = createDraft(0, 'input', '切换类型')
    input.locator = 'ocr'
    input.selector = '#legacy'
    input.visualTemplateId = 88
    input.ocrTarget = createOcrTargetDraft({ text: '用户名' })
    input.extraPayloadJson = JSON.stringify({
      selector: '#advanced',
      ocr_target: { text: 'advanced' },
      trace_label: 'keep'
    })

    const selected = normalizeStepByType(input, 'select_option')

    expect(selected.selector).toBe('')
    expect(selected.visualTemplateId).toBeNull()
    expect(selected.ocrTarget.text).toBe('')
    expect(selected.fieldTarget).toMatchObject({
      text: '',
      role: 'input',
      actionPoint: 'associated_control'
    })
    expect(JSON.parse(selected.extraPayloadJson)).toEqual({
      trace_label: 'keep'
    })
  })
})
