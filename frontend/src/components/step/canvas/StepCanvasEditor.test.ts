import { defineComponent } from 'vue'
import {
  flushPromises,
  shallowMount,
  type VueWrapper
} from '@vue/test-utils'
import { Position, VueFlow, type Edge, type Node } from '@vue-flow/core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StepCanvasEditor from './StepCanvasEditor.vue'
import StepCanvasLegend from './StepCanvasLegend.vue'
import StepCanvasSidebar from './StepCanvasSidebar.vue'
import StepCanvasStatusBar from './StepCanvasStatusBar.vue'
import StepCanvasToolbar from './StepCanvasToolbar.vue'
import type { StepCanvasEdgeData, StepCanvasNodeData } from '@/types/stepCanvas'
import type {
  StepGraphComponentPreview,
  StepStructurePath
} from '@/types/stepGraph'
import {
  createEmptyStepDraft,
  normalizeStepByType,
  type StepDraft,
  type StepValidationErrors
} from '@/utils/steps'

const DialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: {
      type: Boolean,
      required: true
    },
    bodyClass: String,
    modalClass: String
  },
  emits: ['update:modelValue', 'closed'],
  template: '<div class="dialog-stub"><slot /></div>'
})

const ControlsStub = defineComponent({
  name: 'Controls',
  template: '<div class="controls-stub"><slot /></div>'
})

const ControlButtonStub = defineComponent({
  name: 'ControlButton',
  inheritAttrs: false,
  template: '<button v-bind="$attrs" type="button"><slot /></button>'
})

const VueFlowStub = defineComponent({
  name: 'VueFlow',
  inheritAttrs: false,
  props: {
    edges: {
      type: Array,
      default: () => []
    },
    nodes: {
      type: Array,
      default: () => []
    }
  },
  template: '<div class="vue-flow-stub" v-bind="$attrs"><slot /></div>'
})

function makeDrafts(): StepDraft[] {
  const first = createEmptyStepDraft(0)
  first.name = '等待页面稳定'
  const second = createEmptyStepDraft(1)
  second.name = '打开登录页'
  second.type = 'navigate'
  second.url = '/login'
  return [first, second]
}

const mountedWrappers: VueWrapper[] = []
const originalMatchMedia = window.matchMedia

function mountEditor(
  drafts: StepDraft[],
  options: {
    componentPreviews?: Readonly<Record<number, StepGraphComponentPreview>>
    selectedPath?: StepStructurePath | null
  } = {}
): VueWrapper {
  const wrapper = shallowMount(StepCanvasEditor, {
    props: {
      visible: true,
      userId: 3,
      workspaceId: 5,
      testCaseId: 8,
      title: '登录流程',
      testCaseCode: 'TC-LOGIN-001',
      stepDrafts: drafts,
      componentPreviews: options.componentPreviews ?? {},
      selectedPath: options.selectedPath ?? null
    },
    global: {
      stubs: {
        ControlButton: ControlButtonStub,
        Controls: ControlsStub,
        ElButton: true,
        ElDialog: DialogStub,
        ElDrawer: true,
        ElIcon: true,
        VueFlow: VueFlowStub
      }
    }
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

function installMatchMedia(matches: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((query: string): MediaQueryList => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    }))
  })
}

function createFlowStore() {
  return {
    addSelectedNodes: vi.fn(),
    findNode: vi.fn((path: string) => ({
      id: path,
      width: 224,
      height: 96,
      dimensions: {
        width: 224,
        height: 96
      },
      computedPosition: {
        x: 120,
        y: 80,
        z: 1
      }
    })),
    fitView: vi.fn(async (): Promise<void> => undefined),
    getViewport: vi.fn(() => ({ x: 0, y: 0, zoom: 1 })),
    removeSelectedElements: vi.fn(),
    screenToFlowCoordinate: vi.fn(
      (position: { x: number; y: number }): { x: number; y: number } => position
    ),
    setCenter: vi.fn(async (): Promise<void> => undefined),
    updateNode: vi.fn(),
    zoomIn: vi.fn(async (): Promise<void> => undefined),
    zoomOut: vi.fn(async (): Promise<void> => undefined),
    zoomTo: vi.fn(async (): Promise<void> => undefined)
  }
}

interface StepCanvasEditorExposed {
  fitView: () => Promise<void>
  autoLayout: () => Promise<void>
  focusNode: (path: StepStructurePath) => Promise<void>
}

function getEditorVm(wrapper: VueWrapper): StepCanvasEditorExposed {
  return wrapper.vm as unknown as StepCanvasEditorExposed
}

function createDragTransfer(): {
  dropEffect: string
  getData: (mime: string) => string
} {
  return {
    dropEffect: 'none',
    getData: (_mime: string): string => ''
  }
}

afterEach((): void => {
  mountedWrappers.splice(0).forEach((wrapper: VueWrapper): void => {
    wrapper.unmount()
  })
  window.localStorage.clear()
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: originalMatchMedia
  })
  document.body.replaceChildren()
})

describe('StepCanvasEditor shell', (): void => {
  it('applies the fullscreen height chain and cleans up compact body mode', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    await flushPromises()

    expect(document.body.classList.contains('step-canvas-open')).toBe(true)
    expect(wrapper.findComponent(DialogStub).props()).toMatchObject({
      bodyClass: 'step-canvas-dialog-body',
      modalClass: 'step-canvas-overlay'
    })
    expect(wrapper.find('.step-canvas-workbench').exists()).toBe(true)
    expect(wrapper.find('.step-canvas-main').exists()).toBe(true)
    expect(wrapper.find('.step-canvas-stage').exists()).toBe(true)
    expect(wrapper.findComponent(VueFlow).classes()).toContain('step-canvas-flow')

    await wrapper.setProps({ visible: false })
    expect(document.body.classList.contains('step-canvas-open')).toBe(false)

    await wrapper.setProps({ visible: true })
    expect(document.body.classList.contains('step-canvas-open')).toBe(true)

    wrapper.unmount()
    mountedWrappers.splice(mountedWrappers.indexOf(wrapper), 1)
    expect(document.body.classList.contains('step-canvas-open')).toBe(false)
  })

  it('uses the semantic node as the only focus stop and leaves arrow navigation enabled', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    await flushPromises()

    const flow = wrapper.findComponent(VueFlow)
    const nodes = flow.props('nodes') as Array<Node<StepCanvasNodeData>>
    const edges = flow.props('edges') as Array<Edge<StepCanvasEdgeData>>

    expect(nodes.every((node: Node<StepCanvasNodeData>): boolean =>
      node.focusable === false
    )).toBe(true)
    expect(edges.every((edge: Edge<StepCanvasEdgeData>): boolean =>
      edge.focusable === false
    )).toBe(true)
    expect(edges.every((edge: Edge<StepCanvasEdgeData>): boolean =>
      Boolean(
        edge.data?.title.includes('顺序执行关系') &&
        edge.ariaLabel === edge.data.title
      )
    )).toBe(true)
    expect(nodes.every((node: Node<StepCanvasNodeData>): boolean =>
      node.sourcePosition === Position.Bottom
    )).toBe(true)
    expect(nodes.every((node: Node<StepCanvasNodeData>): boolean =>
      node.targetPosition === Position.Top
    )).toBe(true)
  })

  it('names the zoom controls and invokes the Vue Flow viewport commands', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    await flushPromises()

    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()
    flowStore.zoomIn.mockClear()
    flowStore.zoomOut.mockClear()
    flowStore.fitView.mockClear()

    const zoomInButton = wrapper.get('button[aria-label="放大画布"]')
    const zoomOutButton = wrapper.get('button[aria-label="缩小画布"]')
    const fitViewButton = wrapper.get('button[aria-label="适应画布视图"]')

    expect(zoomInButton.attributes('title')).toBe('放大画布')
    expect(zoomOutButton.attributes('title')).toBe('缩小画布')
    expect(fitViewButton.attributes('title')).toBe('适应画布视图')

    await zoomInButton.trigger('click')
    await zoomOutButton.trigger('click')
    await fitViewButton.trigger('click')
    await flushPromises()

    expect(flowStore.zoomIn).toHaveBeenCalledWith({ duration: 180 })
    expect(flowStore.zoomOut).toHaveBeenCalledWith({ duration: 180 })
    expect(flowStore.fitView).toHaveBeenCalledWith({
      padding: 0.15,
      maxZoom: 1.15,
      duration: 180
    })
  })

  it('gates viewport commands until pane ready without Vue Flow warnings', async (): Promise<void> => {
    const warningSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    const flow = wrapper.findComponent(VueFlow)
    await flushPromises()

    expect(wrapper.findComponent(StepCanvasToolbar).props('viewportReady')).toBe(false)
    expect(
      wrapper.get('button[aria-label="放大画布，画布正在初始化"]').attributes()
    ).toMatchObject({
      disabled: '',
      title: '画布视口正在初始化，请稍候'
    })
    expect(flow.attributes('fit-view-on-init')).toBeUndefined()

    flow.vm.$emit('init', flowStore)
    await flushPromises()
    await getEditorVm(wrapper).fitView()
    await getEditorVm(wrapper).autoLayout()
    await getEditorVm(wrapper).focusNode('top:0')
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: '0', bubbles: true })
    )
    await flushPromises()

    expect(flowStore.fitView).not.toHaveBeenCalled()
    expect(flowStore.setCenter).not.toHaveBeenCalled()
    expect(flowStore.zoomTo).not.toHaveBeenCalled()

    flow.vm.$emit('paneReady', flowStore)
    await flushPromises()

    expect(wrapper.findComponent(StepCanvasToolbar).props('viewportReady')).toBe(true)
    expect(flowStore.fitView).toHaveBeenCalledTimes(1)
    expect(wrapper.get('button[aria-label="放大画布"]').attributes('disabled')).toBeUndefined()
    expect(
      warningSpy.mock.calls.some(
        (call: unknown[]): boolean =>
          String(call[0]).includes('Viewport not initialized yet')
      )
    ).toBe(false)
  })

  it('renders the workbench regions and forwards extension events', async (): Promise<void> => {
    const drafts = makeDrafts()
    const wrapper = mountEditor(drafts)
    await flushPromises()

    const toolbar = wrapper.findComponent(StepCanvasToolbar)
    const sidebar = wrapper.findComponent(StepCanvasSidebar)
    const statusBar = wrapper.findComponent(StepCanvasStatusBar)

    expect(toolbar.props('title')).toBe('登录流程')
    expect(sidebar.props('nodes')).toHaveLength(3)
    expect(statusBar.props('stepCount')).toBe(2)

    toolbar.vm.$emit('save')
    toolbar.vm.$emit('close')
    sidebar.vm.$emit('create-step', 'click')
    await flushPromises()

    expect(wrapper.emitted('save')).toHaveLength(1)
    expect(wrapper.emitted('create-step')?.[0]).toEqual(['click'])
    expect(wrapper.emitted('request-close')).toHaveLength(1)
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
  })

  it('keeps external StepDraft business state unchanged during auto layout', async (): Promise<void> => {
    const drafts = makeDrafts()
    const originalDrafts = JSON.stringify(drafts)
    const wrapper = mountEditor(drafts)
    const flowStore = createFlowStore()
    await flushPromises()

    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()
    wrapper.findComponent(StepCanvasToolbar).vm.$emit('auto-layout')
    await flushPromises()

    expect(JSON.stringify(drafts)).toBe(originalDrafts)
    expect(wrapper.emitted('display-state-change')).toBeTruthy()
  })

  it('returns immutable StepDraft arrays for node structure actions', async (): Promise<void> => {
    const drafts = makeDrafts()
    const originalDrafts = JSON.stringify(drafts)
    const wrapper = mountEditor(drafts)
    await flushPromises()

    const flow = wrapper.findComponent(VueFlow)
    const nodes = flow.props('nodes') as Array<Node<StepCanvasNodeData>>
    nodes[1].data?.onDuplicate('top:0')
    await flushPromises()

    const nextDrafts = wrapper.emitted('update:stepDrafts')?.[0]?.[0] as StepDraft[]
    expect(nextDrafts.map((step: StepDraft): string => step.name)).toEqual([
      '等待页面稳定',
      '等待页面稳定',
      '打开登录页'
    ])
    expect(wrapper.emitted('steps-change')?.[0]?.[1]).toMatchObject({
      kind: 'duplicate',
      sourcePath: 'top:0',
      focusPath: 'top:1'
    })
    expect(JSON.stringify(drafts)).toBe(originalDrafts)
  })

  it('drops palette nodes into the root flow through the command history path', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    flowStore.screenToFlowCoordinate.mockReturnValue({
      x: 10_000,
      y: 10_000
    })
    await flushPromises()
    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()

    wrapper.findComponent(StepCanvasSidebar).vm.$emit(
      'palette-drag-start',
      'click'
    )
    const dataTransfer = createDragTransfer()
    const stage = wrapper.get('.step-canvas-stage')
    await stage.trigger('dragover', {
      clientX: 1000,
      clientY: 800,
      dataTransfer
    })
    expect(dataTransfer.dropEffect).toBe('copy')
    expect(wrapper.get('.step-drop-feedback').text()).toContain(
      '释放以新增到当前插入位'
    )

    await stage.trigger('drop', {
      clientX: 1000,
      clientY: 800,
      dataTransfer
    })
    await flushPromises()

    const nextDrafts = wrapper.emitted('update:stepDrafts')?.at(-1)?.[0] as
      StepDraft[]
    expect(nextDrafts.map((step: StepDraft): string => step.type)).toEqual([
      'wait',
      'navigate',
      'click'
    ])
    expect(wrapper.emitted('steps-change')?.at(-1)?.[1]).toMatchObject({
      kind: 'create',
      targetContainerPath: 'root',
      insertionIndex: 2
    })
  })

  it('uses the vertical midpoint to choose a top-to-bottom insertion position', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    await flushPromises()
    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()

    const nodes = wrapper.findComponent(VueFlow).props('nodes') as Array<
      Node<StepCanvasNodeData>
    >
    const firstStep = nodes.find(
      (node: Node<StepCanvasNodeData>): boolean => node.id === 'top:0'
    )
    expect(firstStep).toBeDefined()
    flowStore.screenToFlowCoordinate.mockReturnValue({
      x: (firstStep?.position.x ?? 0) + 8,
      y:
        (firstStep?.position.y ?? 0) +
        Number(firstStep?.height ?? 96) -
        8
    })

    wrapper.findComponent(StepCanvasSidebar).vm.$emit(
      'palette-drag-start',
      'click'
    )
    const stage = wrapper.get('.step-canvas-stage')
    const dataTransfer = createDragTransfer()
    await stage.trigger('dragover', {
      clientX: 200,
      clientY: 200,
      dataTransfer
    })
    expect(wrapper.get('.step-drop-indicator').attributes('style')).toContain(
      'width:'
    )
    await stage.trigger('drop', {
      clientX: 200,
      clientY: 200,
      dataTransfer
    })
    await flushPromises()

    const nextDrafts = wrapper.emitted('update:stepDrafts')?.at(-1)?.[0] as
      StepDraft[]
    expect(nextDrafts.map((step: StepDraft): string => step.type)).toEqual([
      'wait',
      'click',
      'navigate'
    ])
    expect(wrapper.emitted('steps-change')?.at(-1)?.[1]).toMatchObject({
      kind: 'create',
      targetContainerPath: 'root',
      insertionIndex: 1
    })
  })

  it('rejects palette component calls and nested conditions in branch drop zones', async (): Promise<void> => {
    const conditional = createEmptyStepDraft(0)
    conditional.name = '登录状态分支'
    Object.assign(
      conditional,
      normalizeStepByType(conditional, 'conditional_branch')
    )
    const wrapper = mountEditor([conditional])
    const flowStore = createFlowStore()
    await flushPromises()
    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()
    const nodes = wrapper.findComponent(VueFlow).props('nodes') as Array<
      Node<StepCanvasNodeData>
    >
    const branchLane = nodes.find(
      (node: Node<StepCanvasNodeData>): boolean =>
        node.data?.graphNode.kind === 'branch-lane'
    )
    expect(branchLane).toBeDefined()
    flowStore.screenToFlowCoordinate.mockReturnValue({
      x: (branchLane?.position.x ?? 0) + 20,
      y: (branchLane?.position.y ?? 0) + 20
    })

    const stage = wrapper.get('.step-canvas-stage')
    for (const stepType of ['component_call', 'conditional_branch'] as const) {
      wrapper.findComponent(StepCanvasSidebar).vm.$emit(
        'palette-drag-start',
        stepType
      )
      const dataTransfer = createDragTransfer()
      await stage.trigger('dragover', {
        clientX: 300,
        clientY: 200,
        dataTransfer
      })
      expect(wrapper.get('.step-drop-feedback').text()).toContain(
        '分支子步骤不支持 component_call 或 conditional_branch'
      )
      await stage.trigger('drop', {
        clientX: 300,
        clientY: 200,
        dataTransfer
      })
    }
    expect(wrapper.emitted('update:stepDrafts')).toBeUndefined()
  })

  it('renders component steps as collapsible read-only nodes and emits detail navigation', async (): Promise<void> => {
    const componentCall = createEmptyStepDraft(0)
    componentCall.name = '调用登录组件'
    Object.assign(
      componentCall,
      normalizeStepByType(componentCall, 'component_call')
    )
    componentCall.componentId = 42
    const wrapper = mountEditor([componentCall], {
      componentPreviews: {
        42: {
          componentId: 42,
          name: '登录组件',
          status: 'draft',
          loadState: 'ready',
          steps: [
            {
              name: '输入账号',
              type: 'input'
            }
          ]
        }
      }
    })
    await flushPromises()

    let nodes = wrapper.findComponent(VueFlow).props('nodes') as Array<
      Node<StepCanvasNodeData>
    >
    const componentNode = nodes.find(
      (node: Node<StepCanvasNodeData>): boolean =>
        node.data?.graphNode.stepType === 'component_call'
    )
    const previewNode = nodes.find(
      (node: Node<StepCanvasNodeData>): boolean =>
        node.data?.graphNode.kind === 'component-preview'
    )
    expect(componentNode?.data?.canCollapse).toBe(true)
    expect(componentNode?.data?.graphNode.summary).toContain(
      '未发布，仅供预览'
    )
    expect(previewNode).toMatchObject({
      draggable: false,
      data: {
        graphNode: expect.objectContaining({
          editable: false,
          readOnly: true,
          componentId: 42
        })
      }
    })
    componentNode?.data?.onOpenComponent(42)
    expect(wrapper.emitted('open-component')?.[0]).toEqual([42])

    componentNode?.data?.onToggleCollapse('top:0')
    await flushPromises()
    nodes = wrapper.findComponent(VueFlow).props('nodes') as Array<
      Node<StepCanvasNodeData>
    >
    expect(
      nodes.some(
        (node: Node<StepCanvasNodeData>): boolean =>
          node.data?.graphNode.kind === 'component-preview'
      )
    ).toBe(false)
    expect(
      nodes.find(
        (node: Node<StepCanvasNodeData>): boolean => node.id === 'top:0'
      )?.data?.graphNode.hiddenDescendantCount
    ).toBe(1)
  })

  it('switches edge geometry and degrades labels below 60 percent zoom', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    await flushPromises()

    wrapper.findComponent(StepCanvasLegend).vm.$emit('update:connectionStyle', 'step')
    await flushPromises()
    const flow = wrapper.findComponent(VueFlow)
    let edges = flow.props('edges') as Array<Edge<StepCanvasEdgeData>>
    expect(edges.every((edge: Edge<StepCanvasEdgeData>): boolean =>
      edge.data?.connectionStyle === 'step'
    )).toBe(true)

    flow.vm.$emit('move', {
      flowTransform: { x: 0, y: 0, zoom: 0.59 }
    })
    await flushPromises()
    edges = flow.props('edges') as Array<Edge<StepCanvasEdgeData>>
    expect(edges.every((edge: Edge<StepCanvasEdgeData>): boolean =>
      edge.data?.showLabel === false
    )).toBe(true)
  })

  it('aggregates injected validation errors and locates the selected error node', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    const validateStep = (step: StepDraft): StepValidationErrors =>
      step.stepNo === 1
        ? {
            waitMs: '等待时长无效。',
            timeoutMs: '超时时间无效。'
          }
        : {}
    await wrapper.setProps({ validateStepFn: validateStep })
    await flushPromises()

    const statusBar = wrapper.findComponent(StepCanvasStatusBar)
    expect(statusBar.props('errorCount')).toBe(2)
    expect(statusBar.props('errors')).toEqual([
      {
        path: 'top:0',
        nodeLabel: '等待页面稳定',
        messages: ['等待时长无效。', '超时时间无效。']
      }
    ])

    statusBar.vm.$emit('locate-error', 'top:0')
    await flushPromises()

    expect(wrapper.emitted('select-node')?.at(-1)).toEqual(['top:0'])
    expect(wrapper.emitted('locate')?.at(-1)).toEqual(['top:0'])
  })

  it('uses zero-duration viewport commands when reduced motion is requested', async (): Promise<void> => {
    installMatchMedia(true)
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    await flushPromises()

    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()
    await getEditorVm(wrapper).autoLayout()
    await getEditorVm(wrapper).focusNode('top:0')
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: '0', bubbles: true })
    )
    await flushPromises()

    expect(flowStore.fitView).toHaveBeenCalledWith(
      expect.objectContaining({ duration: 0 })
    )
    expect(flowStore.setCenter).toHaveBeenCalledWith(
      expect.any(Number),
      expect.any(Number),
      expect.objectContaining({ duration: 0 })
    )
    expect(flowStore.zoomTo).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ duration: 0 })
    )
  })

  it('supports keyboard creation, ordering, deletion, save, and clean close', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts(), { selectedPath: 'top:0' })
    await flushPromises()

    window.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'ArrowDown',
        altKey: true,
        bubbles: true
      })
    )
    await flushPromises()
    expect(wrapper.emitted('steps-change')?.at(-1)?.[1]).toMatchObject({
      kind: 'reorder',
      sourcePath: 'top:0',
      focusPath: 'top:1'
    })

    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'n', bubbles: true })
    )
    await flushPromises()
    expect(wrapper.emitted('steps-change')?.at(-1)?.[1]).toMatchObject({
      kind: 'create'
    })

    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Delete', bubbles: true })
    )
    await flushPromises()
    expect(wrapper.emitted('steps-change')?.at(-1)?.[1]).toMatchObject({
      kind: 'delete'
    })

    window.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 's',
        ctrlKey: true,
        bubbles: true
      })
    )
    await flushPromises()
    expect(wrapper.emitted('save')).toHaveLength(1)

    await wrapper.setProps({ visible: false })
    const cleanWrapper = mountEditor(makeDrafts())
    await flushPromises()
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    )
    await flushPromises()
    expect(cleanWrapper.emitted('request-close')).toHaveLength(1)
    expect(cleanWrapper.emitted('update:visible')?.at(-1)).toEqual([false])
  })

  it('keeps canvas shortcuts inert inside native and ARIA input controls', async (): Promise<void> => {
    const wrapper = mountEditor(makeDrafts())
    await flushPromises()
    const input = document.createElement('input')
    const combobox = document.createElement('div')
    combobox.setAttribute('role', 'combobox')
    document.body.append(input, combobox)

    input.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 's',
        ctrlKey: true,
        bubbles: true
      })
    )
    combobox.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Delete',
        bubbles: true
      })
    )
    await flushPromises()

    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.emitted('steps-change')).toBeUndefined()
  })

  it('moves DOM focus to the selected node after keyboard navigation', async (): Promise<void> => {
    installMatchMedia(true)
    const wrapper = mountEditor(makeDrafts())
    const flowStore = createFlowStore()
    const container = document.createElement('div')
    container.dataset.id = 'top:0'
    const focusTarget = document.createElement('div')
    focusTarget.className = 'step-execution-node'
    focusTarget.tabIndex = 0
    container.append(focusTarget)
    document.body.append(container)
    await flushPromises()

    wrapper.findComponent(VueFlow).vm.$emit('init', flowStore)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', flowStore)
    await flushPromises()
    await getEditorVm(wrapper).focusNode('top:0')

    expect(document.activeElement).toBe(focusTarget)
  })
})
