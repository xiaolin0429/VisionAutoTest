import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StepCanvasPreviewView from './StepCanvasPreviewView.vue'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: routerPush
  })
}))

const StepCanvasEditorStub = defineComponent({
  name: 'StepCanvasEditor',
  props: {
    visible: Boolean,
    components: {
      type: Array,
      default: () => []
    },
    componentPreviews: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['open-component'],
  template: '<div class="step-canvas-editor-stub" />'
})

describe('StepCanvasPreviewView', (): void => {
  beforeEach((): void => {
    routerPush.mockReset()
  })

  it('routes component preview events to the component detail query contract', async (): Promise<void> => {
    const wrapper = shallowMount(StepCanvasPreviewView, {
      global: {
        stubs: {
          ElButton: true,
          StepCanvasEditor: StepCanvasEditorStub
        }
      }
    })
    const editor = wrapper.findComponent(StepCanvasEditorStub)

    expect(editor.props('components')).toEqual([
      expect.objectContaining({ id: 42 })
    ])
    expect(editor.props('componentPreviews')).toEqual({
      42: expect.objectContaining({ componentId: 42 })
    })

    editor.vm.$emit('open-component', 42)
    await wrapper.vm.$nextTick()

    expect(routerPush).toHaveBeenCalledWith({
      name: 'components',
      query: { componentId: '42' }
    })
    expect(editor.props('visible')).toBe(false)
  })
})
