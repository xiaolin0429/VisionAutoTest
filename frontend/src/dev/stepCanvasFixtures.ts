import type { Component, StepType, Template } from '@/types/models'
import type {
  StepGraphAnnotation,
  StepGraphComponentPreview
} from '@/types/stepGraph'
import {
  createBranchChildStepDraft,
  createEmptyStepDraft,
  createOcrTargetDraft,
  normalizeStepByType,
  type ConditionalBranchDraft,
  type StepDraft
} from '@/utils/steps'

export interface LargeStepCanvasFixture {
  drafts: StepDraft[]
  annotations: StepGraphAnnotation[]
  editableNodeCount: number
  edgeCount: number
}

export interface StepCanvasPreviewFixture {
  drafts: StepDraft[]
  templates: Template[]
  components: Component[]
  componentPreviews: Record<number, StepGraphComponentPreview>
}

function createDraft(
  index: number,
  type: StepType,
  name: string
): StepDraft {
  const draft = normalizeStepByType(createEmptyStepDraft(index), type)
  draft.id = -(index + 1)
  draft.stepNo = index + 1
  draft.name = name
  return draft
}

function createChildDraft(
  index: number,
  type: StepType,
  name: string
): StepDraft {
  const draft = normalizeStepByType(createBranchChildStepDraft(index), type)
  draft.id = -(10_000 + index)
  draft.stepNo = index + 1
  draft.name = name
  return draft
}

export function createLargeStepCanvasFixture(): LargeStepCanvasFixture {
  const editableNodeCount = 150
  const drafts = Array.from(
    { length: editableNodeCount },
    (_value: unknown, index: number): StepDraft => {
      const draft = createDraft(index, 'wait', `性能步骤 ${index + 1}`)
      draft.waitMs = 20 + (index % 5) * 10
      return draft
    }
  )
  const executableEdgeCount = editableNodeCount
  const annotationCount = 180 - executableEdgeCount
  const annotations = Array.from(
    { length: annotationCount },
    (_value: unknown, index: number): StepGraphAnnotation => ({
      id: `performance-annotation-${index + 1}`,
      source: `top:${index}`,
      target: `top:${editableNodeCount - annotationCount + index}`,
      kind: index % 2 === 0 ? 'dependency' : 'parallel',
      label: `性能标注 ${index + 1}`
    })
  )

  return {
    drafts,
    annotations,
    editableNodeCount,
    edgeCount: executableEdgeCount + annotationCount
  }
}

function createTemplate(
  id: number,
  name: string,
  matchStrategy: 'template' | 'ocr'
): Template {
  return {
    id,
    code: `preview-template-${id}`,
    name,
    templateType: 'page',
    matchStrategy,
    thresholdValue: 0.82,
    status: 'active',
    currentBaselineRevisionId: id,
    baselineVersion: 'v1',
    createdAt: '2026-08-15T00:00:00Z',
    updatedAt: '2026-08-15T00:00:00Z',
    imageLabel: `${name}.png`,
    baselineRevisions: [],
    maskRegions: []
  }
}

function createBranch(
  index: number,
  overrides: Partial<ConditionalBranchDraft>
): ConditionalBranchDraft {
  return {
    id: -(20_000 + index),
    branchKey: `branch_${index + 1}`,
    branchName: `分支 ${index + 1}`,
    conditionType: 'selector_exists',
    ocrTarget: createOcrTargetDraft(),
    templateId: null,
    threshold: null,
    selector: '#preview-ready',
    steps: [createChildDraft(index, 'wait', '等待分支稳定')],
    ...overrides
  }
}

export function createStepCanvasPreviewFixture(): StepCanvasPreviewFixture {
  const visualTemplate = createTemplate(101, '登录按钮模板', 'template')
  const ocrTemplate = createTemplate(102, '欢迎文本 OCR', 'ocr')
  const component: Component = {
    id: 42,
    workspaceId: 1,
    code: 'preview-login-component',
    name: '登录公共组件',
    status: 'published',
    description: 'DEV 画布预览使用的本地组件。',
    publishedAt: '2026-08-15T00:00:00Z',
    createdAt: '2026-08-15T00:00:00Z',
    updatedAt: '2026-08-15T00:00:00Z'
  }

  const navigate = createDraft(0, 'navigate', '打开登录页')
  navigate.url = '/login'
  navigate.extraPayloadJson = JSON.stringify({
    trace_label: 'dev-preview'
  })

  const visualInput = createDraft(1, 'input', '输入账号')
  visualInput.locator = 'visual'
  visualInput.visualTemplateId = visualTemplate.id
  visualInput.visualThreshold = 0.86
  visualInput.visualAnchorXRatio = 0.5
  visualInput.visualAnchorYRatio = 0.55
  visualInput.text = 'preview@example.com'
  visualInput.inputMode = 'type'
  visualInput.perCharDelayMs = 40

  const conditional = createDraft(2, 'conditional_branch', '判断登录状态')
  conditional.conditionalBranches = [
    createBranch(0, {
      branchKey: 'selector_ready',
      branchName: 'DOM 已就绪',
      conditionType: 'selector_exists',
      selector: '#dashboard',
      steps: [createChildDraft(0, 'click', '进入工作台')]
    }),
    createBranch(1, {
      branchKey: 'welcome_visible',
      branchName: '欢迎文本可见',
      conditionType: 'ocr_text_visible',
      ocrTarget: createOcrTargetDraft({
        text: '欢迎回来',
        matchMode: 'contains'
      }),
      steps: [createChildDraft(0, 'ocr_assert', '确认欢迎文本')]
    }),
    createBranch(2, {
      branchKey: 'template_visible',
      branchName: '登录按钮可见',
      conditionType: 'template_visible',
      templateId: visualTemplate.id,
      threshold: 0.84,
      steps: [createChildDraft(0, 'template_assert', '确认登录按钮')]
    })
  ]
  conditional.conditionalBranches[0].steps[0].selector = '#dashboard'
  conditional.conditionalBranches[1].steps[0].ocrTarget.text = '欢迎回来'
  conditional.conditionalBranches[1].steps[0].templateId = ocrTemplate.id
  conditional.conditionalBranches[2].steps[0].templateId = visualTemplate.id
  conditional.elseBranchEnabled = true
  conditional.elseBranchName = '默认处理'
  conditional.elseSteps = [createChildDraft(0, 'wait', '等待页面刷新')]

  const componentCall = createDraft(3, 'component_call', '执行登录组件')
  componentCall.componentId = component.id

  const invalidClick = createDraft(4, 'click', '故意保留的错误节点')
  invalidClick.selector = ''

  return {
    drafts: [navigate, visualInput, conditional, componentCall, invalidClick],
    templates: [visualTemplate, ocrTemplate],
    components: [component],
    componentPreviews: {
      [component.id]: {
        componentId: component.id,
        name: component.name,
        status: component.status,
        steps: [
          {
            name: '填写密码',
            type: 'input',
            summary: 'CSS #password'
          },
          {
            name: '点击登录',
            type: 'click',
            summary: '视觉模板 #101'
          }
        ]
      }
    }
  }
}
