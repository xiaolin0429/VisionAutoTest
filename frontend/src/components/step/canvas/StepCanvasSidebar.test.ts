import { defineComponent, nextTick } from 'vue'
import { shallowMount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import StepCanvasSidebar from './StepCanvasSidebar.vue'
import {
  STEP_CANVAS_PALETTE_MIME,
  type StepCanvasPaletteDragPayload
} from '@/types/stepCanvas'
import type { StepGraphNodeDisplayState } from '@/types/stepGraph'
import { projectStepDraftsToGraph } from '@/utils/stepGraph'
import {
  createEmptyStepDraft,
  normalizeStepByType
} from '@/utils/steps'

const SlotStub = defineComponent({
  template: '<div><slot /></div>'
})

interface SidebarVm {
  activeTab: 'library' | 'outline'
}

function createSidebar(
  nodeStates: Readonly<Record<string, StepGraphNodeDisplayState>> = {}
): VueWrapper {
  const componentCall = createEmptyStepDraft(0)
  componentCall.name = '调用登录组件'
  Object.assign(
    componentCall,
    normalizeStepByType(componentCall, 'component_call')
  )
  componentCall.componentId = 42
  const graph = projectStepDraftsToGraph([componentCall], {
    componentPreviews: {
      42: {
        componentId: 42,
        name: '登录组件',
        status: 'published',
        steps: [
          {
            name: '输入账号',
            type: 'input'
          }
        ]
      }
    }
  })
  return shallowMount(StepCanvasSidebar, {
    props: {
      nodes: graph.nodes,
      nodeStates
    },
    global: {
      stubs: {
        ElIcon: SlotStub,
        ElInput: true,
        ElTabPane: SlotStub,
        ElTabs: SlotStub,
        ElTooltip: SlotStub
      }
    }
  })
}

function dispatchPaletteDragStart(
  button: Element
): {
  setData: ReturnType<typeof vi.fn>
  effectAllowed: string
} {
  const dataTransfer = {
    setData: vi.fn(),
    effectAllowed: 'none'
  }
  const event = new Event('dragstart', {
    bubbles: true,
    cancelable: true
  })
  Object.defineProperty(event, 'dataTransfer', {
    configurable: true,
    value: dataTransfer
  })
  button.dispatchEvent(event)
  return dataTransfer
}

describe('StepCanvasSidebar', (): void => {
  it('writes a typed drag payload while retaining click creation', async (): Promise<void> => {
    const wrapper = createSidebar()
    const clickButton = wrapper.get('button[aria-label="添加点击步骤"]')

    expect(clickButton.attributes('draggable')).toBe('true')
    const dataTransfer = dispatchPaletteDragStart(clickButton.element)
    await nextTick()

    expect(dataTransfer.effectAllowed).toBe('copy')
    expect(dataTransfer.setData).toHaveBeenCalledTimes(1)
    const [mime, serialized] = dataTransfer.setData.mock.calls[0] as [
      string,
      string
    ]
    expect(mime).toBe(STEP_CANVAS_PALETTE_MIME)
    expect(JSON.parse(serialized) as StepCanvasPaletteDragPayload).toEqual({
      stepType: 'click'
    })
    expect(wrapper.emitted('palette-drag-start')?.[0]).toEqual(['click'])

    await clickButton.trigger('click')
    expect(wrapper.emitted('create-step')?.[0]).toEqual(['click'])
  })

  it('renders a hierarchical outline with synchronized collapse controls', async (): Promise<void> => {
    const wrapper = createSidebar({
      root: { collapsed: true }
    })
    ;(wrapper.vm as unknown as SidebarVm).activeTab = 'outline'
    await nextTick()

    let rows = wrapper.findAll('[role="treeitem"]')
    expect(rows).toHaveLength(1)
    expect(rows[0].attributes()).toMatchObject({
      'aria-expanded': 'false',
      'aria-level': '1'
    })
    const expandButton = wrapper.get('button[aria-label*="展开用例根节点"]')
    expect(expandButton.attributes('aria-label')).toContain('隐藏 2 个节点')
    await expandButton.trigger('click')
    expect(wrapper.emitted('toggle-collapse')?.[0]).toEqual(['root'])

    await wrapper.setProps({
      nodeStates: {
        'top:0': { collapsed: true }
      }
    })
    rows = wrapper.findAll('[role="treeitem"]')
    expect([
      rows[0].attributes('aria-level'),
      rows[1].attributes('aria-level')
    ]).toEqual([
      '1',
      '2'
    ])
    expect(
      wrapper.get('button[aria-label*="展开调用登录组件"]').attributes(
        'aria-label'
      )
    ).toContain('隐藏 1 个节点')
  })
})
