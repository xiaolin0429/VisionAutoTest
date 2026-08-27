import { defineComponent } from 'vue'
import { shallowMount, type VueWrapper } from '@vue/test-utils'
import { Position, type NodeProps } from '@vue-flow/core'
import { describe, expect, it, vi } from 'vitest'

import StepCanvasInspectorContent from './StepCanvasInspectorContent.vue'
import StepCanvasLegend from './StepCanvasLegend.vue'
import StepCanvasNode from './StepCanvasNode.vue'
import StepCanvasStatusBar from './StepCanvasStatusBar.vue'
import stepCanvasStatusBarSource from './StepCanvasStatusBar.vue?raw'
import StepCanvasToolbar from './StepCanvasToolbar.vue'
import type { StepCanvasNodeData } from '@/types/stepCanvas'
import type { StepGraphNode } from '@/types/stepGraph'
import { projectStepDraftsToGraph } from '@/utils/stepGraph'
import { createEmptyStepDraft } from '@/utils/steps'

const TooltipStub = defineComponent({
  name: 'ElTooltip',
  template: '<div class="tooltip-stub"><slot /></div>'
})

const PopoverStub = defineComponent({
  name: 'ElPopover',
  template: '<div><slot name="reference" /><slot /></div>'
})

const ButtonStub = defineComponent({
  name: 'ElButton',
  inheritAttrs: false,
  props: {
    circle: Boolean,
    color: String,
    disabled: Boolean,
    icon: [Object, Function],
    loading: Boolean,
    plain: Boolean,
    text: Boolean,
    type: String
  },
  template: '<button v-bind="$attrs" :disabled="disabled" type="button"><slot /></button>'
})

const ButtonGroupStub = defineComponent({
  name: 'ElButtonGroup',
  template: '<div><slot /></div>'
})

const HandleStub = defineComponent({
  name: 'Handle',
  inheritAttrs: false,
  template: '<span class="handle-stub" v-bind="$attrs" />'
})

function createGraphNode(
  overrides: Partial<StepGraphNode> = {}
): StepGraphNode {
  const draft = createEmptyStepDraft(0)
  draft.name = '提交表单'
  draft.type = 'click'
  draft.selector = '#submit'
  const node = projectStepDraftsToGraph([draft]).nodes[1]
  return {
    ...node,
    ...overrides
  }
}

function mountNode(
  graphNode: StepGraphNode,
  options: {
    selected?: boolean
    readOnly?: boolean
  } = {}
): {
  wrapper: VueWrapper
  openInspector: ReturnType<typeof vi.fn>
} {
  const openInspector = vi.fn()
  const data: StepCanvasNodeData = {
    graphNode: {
      ...graphNode,
      readOnly: options.readOnly ?? graphNode.readOnly
    },
    palette: {
      background: '#eff6ff',
      border: '#2563eb'
    },
    shape: 'rectangle',
    collapsed: false,
    canCollapse: true,
    onToggleCollapse: vi.fn(),
    onAddAfter: vi.fn(),
    onDuplicate: vi.fn(),
    onMore: vi.fn(),
    onOpenInspector: openInspector,
    onOpenComponent: vi.fn()
  }
  const props: NodeProps<StepCanvasNodeData> = {
    id: graphNode.path,
    type: 'step-node',
    selected: options.selected ?? false,
    connectable: false,
    position: { x: 0, y: 0 },
    dimensions: {
      width: graphNode.width,
      height: graphNode.height
    },
    dragging: false,
    resizing: false,
    zIndex: 1,
    data,
    events: {} as NodeProps<StepCanvasNodeData>['events']
  }

  return {
    wrapper: shallowMount(StepCanvasNode, {
      props,
      global: {
        stubs: {
          ElIcon: true,
          ElTooltip: TooltipStub,
          Handle: HandleStub
        }
      }
    }),
    openInspector
  }
}

describe('step canvas accessibility semantics', (): void => {
  it('supports Tab stops and arrow-key traversal in toolbar and inspector commands', async (): Promise<void> => {
    const toolbar = shallowMount(StepCanvasToolbar, {
      attachTo: document.body,
      props: {
        title: '登录流程',
        mode: 'desktop',
        canUndo: true,
        canRedo: true
      },
      global: {
        stubs: {
          ElButton: ButtonStub,
          ElButtonGroup: ButtonGroupStub,
          ElDropdown: true,
          ElDropdownItem: true,
          ElDropdownMenu: true,
          ElTooltip: TooltipStub
        }
      }
    })
    const graphNode = createGraphNode()
    const selectedStep = createEmptyStepDraft(0)
    const inspector = shallowMount(StepCanvasInspectorContent, {
      attachTo: document.body,
      props: {
        activeTab: 'config',
        selectedNode: graphNode,
        selectedStep,
        selectedPaths: [graphNode.path],
        getStepTemplateOptionsFn: () => []
      },
      global: {
        stubs: {
          ElButton: ButtonStub,
          ElInput: true,
          ElOption: true,
          ElRadioButton: true,
          ElRadioGroup: true,
          ElSelect: true,
          ElTooltip: TooltipStub
        }
      }
    })

    expect(toolbar.get('[role="toolbar"]').attributes('aria-label')).toBe(
      '步骤画布命令'
    )
    const toolbarButtons = toolbar.findAll('button')
    toolbarButtons[0].element.focus()
    await toolbarButtons[0].trigger('keydown', { key: 'ArrowRight' })
    expect(document.activeElement).toBe(toolbarButtons[1].element)

    const commandToolbar = inspector.get('[role="toolbar"]')
    expect(commandToolbar.attributes('aria-label')).toBe('所选步骤命令')
    const commandButtons = commandToolbar.findAll('button')
    commandButtons[0].element.focus()
    await commandButtons[0].trigger('keydown', { key: 'ArrowRight' })
    expect(document.activeElement).toBe(commandButtons[1].element)
    commandButtons.forEach((button): void => {
      expect(button.attributes('aria-label')).toBeTruthy()
      expect(button.attributes('tabindex')).not.toBe('-1')
    })

    inspector.unmount()
    toolbar.unmount()
  })

  it('exposes keyboard focus, selection, errors, and named icon actions without color-only state', async (): Promise<void> => {
    const { wrapper, openInspector } = mountNode(
      createGraphNode({ errorCount: 2 }),
      { selected: true }
    )
    const node = wrapper.get('.step-execution-node')

    expect(node.attributes()).toMatchObject({
      role: 'button',
      tabindex: '0',
      'aria-keyshortcuts': 'Enter',
      'aria-selected': 'true',
      'aria-invalid': 'true'
    })
    expect(node.attributes('aria-label')).toContain('2 个配置错误')
    expect(wrapper.get('.error-badge').text()).toBe('2 个配置错误')
    expect(wrapper.findAll('.selection-corner')).toHaveLength(4)
    expect(wrapper.find('.tooltip-stub').exists()).toBe(false)
    const handles = wrapper.findAll('.handle-stub')
    expect(handles).toHaveLength(2)
    expect(handles[0].attributes()).toMatchObject({
      role: 'img',
      position: Position.Top,
      title: '步骤“提交表单”顺序执行输入端口',
      'aria-label': '步骤“提交表单”顺序执行输入端口'
    })
    expect(handles[1].attributes()).toMatchObject({
      role: 'img',
      position: Position.Bottom,
      title: '步骤“提交表单”顺序执行输出端口',
      'aria-label': '步骤“提交表单”顺序执行输出端口'
    })
    wrapper.findAll('button').forEach((button): void => {
      expect(button.attributes('aria-label')).toBeTruthy()
    })

    await node.trigger('keydown', { key: 'Enter' })
    expect(openInspector).toHaveBeenCalledWith('top:0')
  })

  it('marks read-only nodes structurally in addition to dashed styling', (): void => {
    const { wrapper } = mountNode(createGraphNode(), { readOnly: true })
    const node = wrapper.get('.step-execution-node')

    expect(node.classes()).toContain('is-read-only')
    expect(node.attributes('aria-readonly')).toBe('true')
  })

  it('keeps edge meanings and validation status available as text and patterns', (): void => {
    const legend = shallowMount(StepCanvasLegend, {
      props: {
        connectionStyle: 'straight',
        showEdgeLabels: true
      }
    })
    const status = shallowMount(StepCanvasStatusBar, {
      props: {
        stepCount: 5,
        branchCount: 2,
        componentCount: 1,
        errorCount: 3,
        message: '已完成排序，步骤结构已更新。'
      },
      global: {
        stubs: {
          ElIcon: true,
          ElPopover: PopoverStub
        }
      }
    })

    expect(legend.text()).toContain('顺序')
    expect(legend.text()).toContain('依赖 · 仅标注')
    expect(legend.text()).toContain('并行 · 仅标注')
    expect(legend.findAll('.legend-line.is-solid')).toHaveLength(2)
    expect(legend.findAll('.legend-line.is-double')).toHaveLength(1)
    expect(status.text()).toContain('3 个配置错误')
    expect(status.get('[role="status"]').text()).toContain('步骤结构已更新')
  })

  it('keeps the 390px status bar compact without hiding save or error details', (): void => {
    const originalInnerWidth = window.innerWidth
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 390
    })
    const message = '保存失败：服务端步骤配置无效，请修复后重试。'
    const status = shallowMount(StepCanvasStatusBar, {
      attachTo: document.body,
      props: {
        stepCount: 150,
        branchCount: 18,
        componentCount: 12,
        selectedCount: 4,
        errorCount: 3,
        message
      },
      global: {
        stubs: {
          ElIcon: true,
          ElPopover: PopoverStub
        }
      }
    })

    try {
      const mobileBaseRule = stepCanvasStatusBarSource.match(
        /\.step-canvas-status-bar\s*\{([^}]*)\}/
      )?.[1]
      expect(window.innerWidth).toBe(390)
      expect(mobileBaseRule).toContain('height: 32px')
      expect(mobileBaseRule).toContain('min-width: 0')
      expect(mobileBaseRule).toContain('overflow: hidden')
      expect(stepCanvasStatusBarSource).toContain('@media (min-width: 640px)')
      expect(status.get('.status-branch-count').text()).toBe('18 个分支')
      expect(status.get('.status-label-compact').text()).toBe('150 步')
      expect(status.get('.status-message-button').attributes()).toMatchObject({
        'aria-label': `画布状态：${message}`,
        title: message
      })
      expect(status.get('.status-message-detail').text()).toBe(message)
      expect(status.get('.status-error-button').attributes('aria-label')).toBe(
        '3 个配置错误'
      )
      expect(status.get('[role="status"]').text()).toBe(message)
    } finally {
      status.unmount()
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        value: originalInnerWidth
      })
    }
  })
})
