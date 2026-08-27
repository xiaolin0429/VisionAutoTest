import { createPinia, setActivePinia } from 'pinia'
import {
  defineComponent,
  h,
  type VNode
} from 'vue'
import {
  flushPromises,
  shallowMount,
  type VueWrapper
} from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StepEditorDialog from '@/components/step/StepEditorDialog.vue'
import ComponentsView from '@/views/ComponentsView.vue'
import TestCasesView from '@/views/TestCasesView.vue'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import type {
  Component,
  Step,
  StepWritePayload,
  Template,
  TestCase
} from '@/types/models'
import type { EditableStepPath } from '@/types/stepGraph'
import {
  createEmptyStepDraft,
  type StepDraft
} from '@/utils/steps'

const routerState = vi.hoisted(() => ({
  route: {
    query: {} as Record<string, string>
  },
  push: vi.fn(),
  replace: vi.fn()
}))

const testCaseApi = vi.hoisted(() => ({
  cloneTestCase: vi.fn(),
  createTestCase: vi.fn(),
  getTestCaseDetail: vi.fn(),
  listTestCases: vi.fn(),
  replaceTestCaseSteps: vi.fn(),
  updateTestCase: vi.fn()
}))

const componentApi = vi.hoisted(() => ({
  createComponent: vi.fn(),
  getComponentDetail: vi.fn(),
  getComponentSteps: vi.fn(),
  listComponents: vi.fn(),
  replaceComponentSteps: vi.fn(),
  updateComponent: vi.fn()
}))

const templateApi = vi.hoisted(() => ({
  listTemplates: vi.fn()
}))

const canvasMarkSaved = vi.fn()
const canvasLocate = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => routerState.route,
  useRouter: () => ({
    push: routerState.push,
    replace: routerState.replace
  })
}))

vi.mock('@/api/modules/testCases', () => testCaseApi)
vi.mock('@/api/modules/components', () => componentApi)
vi.mock('@/api/modules/templates', () => templateApi)
vi.mock('@/api/modules/workspaces', () => ({
  getWorkspaceExecutionReadiness: vi.fn(async () => ({
    issues: []
  }))
}))

const StepCanvasEditorStub = defineComponent({
  name: 'StepCanvasEditor',
  props: {
    visible: Boolean,
    userId: Number,
    workspaceId: Number,
    testCaseId: Number,
    title: String,
    testCaseCode: String,
    stepDrafts: {
      type: Array,
      default: () => []
    },
    selectedPath: {
      type: String,
      default: null
    },
    saving: Boolean,
    statusMessage: String,
    templates: Array,
    components: Array,
    componentPreviews: Object,
    allowComponentCall: Boolean,
    validateStepFn: Function,
    getStepTemplateOptionsFn: Function,
    getStepTemplateHintFn: Function,
    formatComponentOptionLabelFn: Function
  },
  emits: [
    'update:visible',
    'update:selectedPath',
    'update:step-drafts',
    'save',
    'closed',
    'ready',
    'open-component',
    'request-component-previews'
  ],
  methods: {
    markSaved(drafts: StepDraft[]): void {
      canvasMarkSaved(drafts)
    },
    async locate(path: EditableStepPath): Promise<void> {
      canvasLocate(path)
    }
  },
  render(): VNode {
    return h('div', { class: 'step-canvas-editor-stub' })
  }
})

function createStep(
  stepNo: number,
  type: Step['type'] = 'wait'
): Step {
  return {
    id: stepNo,
    stepNo,
    name: type === 'wait' ? '等待稳定' : '打开登录页',
    type,
    templateId: null,
    componentId: null,
    target: '',
    note: '',
    payloadJson:
      type === 'wait'
        ? { ms: 100 }
        : { url: '/login', wait_until: 'load' },
    timeoutMs: 5000,
    retryTimes: 0
  }
}

function createTestCase(steps: Step[] = [
  createStep(1),
  createStep(2, 'navigate')
]): TestCase {
  return {
    id: 8,
    code: 'TC-LOGIN-001',
    name: '登录流程',
    status: 'draft',
    priority: 'p1',
    description: '',
    createdAt: '2026-08-15T00:00:00Z',
    updatedAt: '2026-08-15T00:00:00Z',
    componentCount: 0,
    steps
  }
}

function createComponent(): Component {
  return {
    id: 11,
    workspaceId: 5,
    code: 'login-component',
    name: '登录组件',
    status: 'draft',
    description: '',
    publishedAt: null,
    createdAt: '2026-08-15T00:00:00Z',
    updatedAt: '2026-08-15T00:00:00Z'
  }
}

function createTemplate(
  id: number,
  matchStrategy: 'template' | 'ocr',
  name: string
): Template {
  return {
    id,
    code: `template-${id}`,
    name,
    templateType: 'page',
    matchStrategy,
    thresholdValue: 0.8,
    status: 'active',
    currentBaselineRevisionId: id,
    baselineVersion: 'v1',
    createdAt: '2026-08-15T00:00:00Z',
    updatedAt: '2026-08-15T00:00:00Z',
    imageLabel: '',
    baselineRevisions: [],
    maskRegions: []
  }
}

async function mountTestCasesView(): Promise<VueWrapper> {
  const wrapper = shallowMount(TestCasesView, {
    global: {
      stubs: {
        StepCanvasEditor: StepCanvasEditorStub,
        ElButton: true,
        ElDialog: true,
        ElEmpty: true,
        ElInput: true,
        ElOption: true,
        ElSelect: true,
        ElTable: true,
        ElTableColumn: true
      },
      directives: {
        loading: {}
      }
    }
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach((): void => {
  window.localStorage.clear()
  setActivePinia(createPinia())
  const authStore = useAuthStore()
  const workspaceStore = useWorkspaceStore()
  authStore.user = {
    id: 3,
    username: 'tester',
    displayName: 'Tester'
  }
  workspaceStore.currentWorkspaceId = 5

  routerState.route.query = {}
  routerState.push.mockReset()
  routerState.replace.mockReset()
  canvasMarkSaved.mockReset()
  canvasLocate.mockReset()

  const testCase = createTestCase()
  testCaseApi.listTestCases.mockReset()
  testCaseApi.listTestCases.mockResolvedValue([testCase])
  testCaseApi.getTestCaseDetail.mockReset()
  testCaseApi.getTestCaseDetail.mockResolvedValue(testCase)
  testCaseApi.replaceTestCaseSteps.mockReset()
  testCaseApi.replaceTestCaseSteps.mockResolvedValue(testCase.steps)
  testCaseApi.cloneTestCase.mockReset()
  testCaseApi.createTestCase.mockReset()
  testCaseApi.updateTestCase.mockReset()

  const component = createComponent()
  componentApi.listComponents.mockReset()
  componentApi.listComponents.mockResolvedValue([component])
  componentApi.getComponentDetail.mockReset()
  componentApi.getComponentDetail.mockResolvedValue(component)
  componentApi.getComponentSteps.mockReset()
  componentApi.getComponentSteps.mockResolvedValue([createStep(1)])
  componentApi.replaceComponentSteps.mockReset()
  componentApi.createComponent.mockReset()
  componentApi.updateComponent.mockReset()

  templateApi.listTemplates.mockReset()
  templateApi.listTemplates.mockResolvedValue([
    createTemplate(101, 'template', '视觉模板'),
    createTemplate(102, 'ocr', 'OCR 模板')
  ])
})

describe('step editor view integration', (): void => {
  it('opens TestCasesView repair query in StepCanvasEditor with current scope and selected node', async (): Promise<void> => {
    routerState.route.query = {
      testCaseId: '8',
      stepNo: '2'
    }

    const wrapper = await mountTestCasesView()
    const canvas = wrapper.findComponent({ name: 'StepCanvasEditor' })

    expect(canvas.exists()).toBe(true)
    expect(canvas.props()).toMatchObject({
      visible: true,
      userId: 3,
      workspaceId: 5,
      testCaseId: 8,
      selectedPath: 'top:1',
      allowComponentCall: true
    })
    expect(canvas.props('stepDrafts')).toHaveLength(2)
    expect(canvas.props('validateStepFn')).toEqual(expect.any(Function))
    expect(canvas.props('getStepTemplateOptionsFn')).toEqual(
      expect.any(Function)
    )
    expect(wrapper.findComponent(StepEditorDialog).exists()).toBe(false)
  })

  it('keeps the case canvas open and preserves continuous drafts after backend validation failure', async (): Promise<void> => {
    routerState.route.query = {
      testCaseId: '8',
      stepNo: '1'
    }
    testCaseApi.replaceTestCaseSteps.mockRejectedValue(
      new ApiError(
        'STEP_CONFIGURATION_INVALID',
        '服务端步骤配置无效。',
        422
      )
    )
    const wrapper = await mountTestCasesView()
    const canvas = wrapper.findComponent({ name: 'StepCanvasEditor' })
    const waitDraft = createEmptyStepDraft(0)
    waitDraft.stepNo = 9
    const navigateDraft = createEmptyStepDraft(1)
    navigateDraft.stepNo = 12
    navigateDraft.type = 'navigate'
    navigateDraft.url = '/next'

    canvas.vm.$emit('save', [navigateDraft, waitDraft])
    await flushPromises()

    const payload = testCaseApi.replaceTestCaseSteps.mock.calls[0][1] as
      StepWritePayload[]
    expect(payload.map((item: StepWritePayload): number => item.stepNo)).toEqual([
      1,
      2
    ])
    expect(wrapper.findComponent({ name: 'StepCanvasEditor' }).props()).toMatchObject({
      visible: true,
      statusMessage: '服务端步骤配置无效。'
    })
    expect(canvasMarkSaved).not.toHaveBeenCalled()
  })

  it('refreshes details, resets the canvas baseline, and closes only after save succeeds', async (): Promise<void> => {
    routerState.route.query = { testCaseId: '8' }
    const refreshedCase = createTestCase([createStep(1, 'navigate')])
    testCaseApi.getTestCaseDetail
      .mockResolvedValueOnce(createTestCase())
      .mockResolvedValueOnce(refreshedCase)
    const wrapper = await mountTestCasesView()
    const canvas = wrapper.findComponent({ name: 'StepCanvasEditor' })
    const navigateDraft = createEmptyStepDraft(0)
    navigateDraft.type = 'navigate'
    navigateDraft.url = '/saved'

    canvas.vm.$emit('save', [navigateDraft])
    await flushPromises()
    await flushPromises()

    expect(testCaseApi.getTestCaseDetail).toHaveBeenCalledTimes(2)
    expect(canvasMarkSaved).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent({ name: 'StepCanvasEditor' }).props('visible')).toBe(
      false
    )
  })

  it('deduplicates component preview loading and routes the canvas detail command', async (): Promise<void> => {
    routerState.route.query = {
      testCaseId: '8',
      stepNo: '1'
    }
    const firstCall = createStep(1, 'component_call')
    firstCall.componentId = 11
    const secondCall = createStep(2, 'component_call')
    secondCall.componentId = 11
    const testCase = createTestCase([firstCall, secondCall])
    testCaseApi.listTestCases.mockResolvedValue([testCase])
    testCaseApi.getTestCaseDetail.mockResolvedValue(testCase)

    const wrapper = await mountTestCasesView()
    await flushPromises()
    const canvas = wrapper.findComponent({ name: 'StepCanvasEditor' })

    expect(componentApi.getComponentDetail).toHaveBeenCalledTimes(1)
    expect(componentApi.getComponentDetail).toHaveBeenCalledWith(11)
    expect(componentApi.getComponentSteps).toHaveBeenCalledTimes(1)
    expect(componentApi.getComponentSteps).toHaveBeenCalledWith(11)
    expect(canvas.props('componentPreviews')).toEqual({
      11: expect.objectContaining({
        componentId: 11,
        name: '登录组件',
        status: 'draft',
        loadState: 'ready',
        steps: [
          expect.objectContaining({
            name: '等待稳定',
            type: 'wait'
          })
        ]
      })
    })

    canvas.vm.$emit('open-component', 11)
    expect(routerState.push).toHaveBeenCalledWith({
      name: 'components',
      query: { componentId: '11' }
    })
  })

  it('keeps the component call visible when its read-only preview fails to load', async (): Promise<void> => {
    routerState.route.query = {
      testCaseId: '8',
      stepNo: '1'
    }
    const componentCall = createStep(1, 'component_call')
    componentCall.componentId = 11
    const testCase = createTestCase([componentCall])
    testCaseApi.listTestCases.mockResolvedValue([testCase])
    testCaseApi.getTestCaseDetail.mockResolvedValue(testCase)
    componentApi.getComponentSteps.mockRejectedValue(
      new Error('组件步骤接口不可用')
    )

    const wrapper = await mountTestCasesView()
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'StepCanvasEditor' }).props(
        'componentPreviews'
      )
    ).toEqual({
      11: expect.objectContaining({
        componentId: 11,
        loadState: 'error',
        errorMessage: '组件步骤接口不可用',
        steps: []
      })
    })
  })

  it('keeps ComponentsView on StepEditorDialog with component calls disabled', async (): Promise<void> => {
    routerState.route.query = { componentId: '11' }
    const wrapper = shallowMount(ComponentsView, {
      global: {
        stubs: {
          ElButton: true,
          ElDialog: true,
          ElEmpty: true,
          ElForm: true,
          ElFormItem: true,
          ElInput: true,
          ElOption: true,
          ElScrollbar: true,
          ElSelect: true,
          ElTable: true,
          ElTableColumn: true
        },
        directives: {
          loading: {}
        }
      }
    })
    await flushPromises()
    await flushPromises()

    const dialog = wrapper.findComponent(StepEditorDialog)
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('allowComponentCall')).toBe(false)
    expect(
      (dialog.props('stepTypeOptions') as Array<{ value: string }>).map(
        (option: { value: string }): string => option.value
      )
    ).toEqual([
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
    ])
    expect(wrapper.findComponent({ name: 'StepCanvasEditor' }).exists()).toBe(
      false
    )
  })

  it('locates a routed component even when it is outside the loaded list page', async (): Promise<void> => {
    routerState.route.query = { componentId: '11' }
    componentApi.listComponents.mockResolvedValue([])
    shallowMount(ComponentsView, {
      global: {
        stubs: {
          ElButton: true,
          ElDialog: true,
          ElEmpty: true,
          ElForm: true,
          ElFormItem: true,
          ElInput: true,
          ElOption: true,
          ElScrollbar: true,
          ElSelect: true,
          ElTable: true,
          ElTableColumn: true
        },
        directives: {
          loading: {}
        }
      }
    })
    await flushPromises()
    await flushPromises()

    expect(componentApi.getComponentDetail).toHaveBeenCalledWith(11)
    expect(componentApi.getComponentSteps).toHaveBeenCalledWith(11)
    expect(componentApi.getComponentDetail).toHaveBeenCalledTimes(1)
    expect(componentApi.getComponentSteps).toHaveBeenCalledTimes(1)
  })

  it('keeps visual locator templates and complete save payloads in the ComponentsView legacy editor', async (): Promise<void> => {
    routerState.route.query = { componentId: '11', stepNo: '1' }
    const wrapper = shallowMount(ComponentsView, {
      global: {
        stubs: {
          ElButton: true,
          ElDialog: true,
          ElEmpty: true,
          ElForm: true,
          ElFormItem: true,
          ElInput: true,
          ElOption: true,
          ElScrollbar: true,
          ElSelect: true,
          ElTable: true,
          ElTableColumn: true
        },
        directives: {
          loading: {}
        }
      }
    })
    await flushPromises()
    await flushPromises()

    const dialog = wrapper.findComponent(StepEditorDialog)
    const getTemplateOptions = dialog.props(
      'getStepTemplateOptionsFn'
    ) as (step: StepDraft) => Array<{ id: number; label: string }>
    const draft = (dialog.props('stepDrafts') as StepDraft[])[0]
    draft.type = 'click'
    draft.name = '视觉点击'
    draft.locator = 'visual'
    draft.visualTemplateId = 101
    draft.visualThreshold = 0.88
    draft.extraPayloadJson = JSON.stringify({
      component_extension: 'kept',
      template_id: 999
    })

    expect(getTemplateOptions(draft)).toEqual([
      {
        id: 101,
        label: '视觉模板 (#101) · active'
      }
    ])

    dialog.vm.$emit('save')
    await flushPromises()
    await flushPromises()

    expect(componentApi.replaceComponentSteps).toHaveBeenCalledTimes(1)
    expect(componentApi.replaceComponentSteps.mock.calls[0]).toEqual([
      11,
      [
        expect.objectContaining({
          stepNo: 1,
          type: 'click',
          name: '视觉点击',
          payloadJson: expect.objectContaining({
            component_extension: 'kept',
            locator: 'visual',
            template_id: 101,
            threshold: 0.88,
            anchor_x_ratio: 0.5,
            anchor_y_ratio: 0.5
          })
        })
      ]
    ])
  })
})
