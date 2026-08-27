import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { ElInput } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProfileFormDialog from './ProfileFormDialog.vue'

const environmentApi = vi.hoisted(() => ({
  createEnvironmentProfile: vi.fn(),
  updateEnvironmentProfile: vi.fn()
}))

vi.mock('@/api/modules/environments', () => environmentApi)

const DialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: Boolean },
  setup(props, { slots }) {
    return () => props.modelValue ? h('div', slots.default?.()) : null
  }
})

describe('ProfileFormDialog base URL validation', (): void => {
  beforeEach((): void => {
    environmentApi.createEnvironmentProfile.mockReset()
    environmentApi.updateEnvironmentProfile.mockReset()
  })

  it('shows the field error as soon as an invalid edited URL loses focus', async (): Promise<void> => {
    const wrapper = mount(ProfileFormDialog, {
      props: {
        visible: false,
        mode: 'edit',
        profile: {
          id: 3,
          workspaceId: 1,
          name: '历史环境',
          baseUrl: 'www.example.com',
          description: '',
          status: 'active',
          variableCount: 0,
          createdAt: '',
          updatedAt: ''
        }
      },
      global: {
        components: {
          ElDialog: DialogStub,
          ElInput
        },
        stubs: {
          ElButton: true,
          ElOption: true,
          ElSelect: true
        }
      }
    })

    await wrapper.setProps({ visible: true })
    await nextTick()

    const baseUrlInput = wrapper.find('input[placeholder="https://example.test"]')
    await baseUrlInput.setValue('e2e.invalid.local')
    await baseUrlInput.trigger('focusout')
    await nextTick()

    expect(wrapper.text()).toContain('请输入包含 http:// 或 https:// 的完整地址')
    expect(environmentApi.updateEnvironmentProfile).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})
