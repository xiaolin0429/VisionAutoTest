import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OcrTargetFields from './OcrTargetFields.vue'
import { createOcrTargetDraft } from '@/utils/steps'

const elementStubs = {
  ElCheckbox: true,
  ElInput: true,
  ElInputNumber: true,
  ElOption: true,
  ElSelect: true,
  ElSwitch: true
}

describe('OcrTargetFields', (): void => {
  it('renders the complete reusable OCR target contract', (): void => {
    const wrapper = shallowMount(OcrTargetFields, {
      props: {
        target: createOcrTargetDraft(),
        title: '字段目标'
      },
      global: {
        stubs: elementStubs
      }
    })

    for (const label of [
      '字段目标',
      '目标文字',
      '匹配模式',
      '匹配序号',
      '扫描范围',
      '语言档案',
      '角色提示',
      '操作点',
      '最低 OCR 置信度',
      '最低综合分',
      '歧义分差',
      '使用相对文字关系消歧'
    ]) {
      expect(wrapper.text()).toContain(label)
    }
  })

  it('shows relation fields and field-level validation errors', (): void => {
    const target = createOcrTargetDraft({
      text: '(',
      matchMode: 'regex',
      minConfidence: 2,
      relation: {
        type: 'right_of',
        anchorText: '',
        maxDistanceRatio: -1
      }
    })
    const wrapper = shallowMount(OcrTargetFields, {
      props: { target },
      global: {
        stubs: elementStubs
      }
    })

    expect(wrapper.text()).toContain('关系类型')
    expect(wrapper.text()).toContain('锚点文字')
    expect(wrapper.text()).toContain('最大距离比例')
    expect(wrapper.text()).toContain('OCR 正则表达式无效')
    expect(wrapper.text()).toContain('最低 OCR 置信度必须在 0 到 1 之间')
    expect(wrapper.text()).toContain('OCR 关系必须填写锚点文字')
  })
})
