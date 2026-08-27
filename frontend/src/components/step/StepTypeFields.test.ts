import { defineComponent } from 'vue'
import { shallowMount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BranchChildStepFields from './BranchChildStepFields.vue'
import ConditionalBranchFields from './ConditionalBranchFields.vue'
import ConditionalBranchMetadataFields from './ConditionalBranchMetadataFields.vue'
import OcrTargetFields from './OcrTargetFields.vue'
import StepTypeFields from './StepTypeFields.vue'
import {
  createEmptyStepDraft,
  normalizeStepByType,
  type StepDraft,
  type StepTemplateOption,
  type StepTypeOption,
  type StepValidationErrors
} from '@/utils/steps'
import type { LocatorType, StepType, Template } from '@/types/models'

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: {
    label: {
      type: String,
      required: true
    }
  },
  template: '<span class="el-option">{{ label }}</span>'
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  template: '<div class="el-select"><slot /></div>'
})

const elementStubs = {
  ElButton: true,
  ElCheckbox: true,
  ElInput: true,
  ElInputNumber: true,
  ElOption: ElOptionStub,
  ElSelect: ElSelectStub,
  ElSwitch: true
}

function makeStep(type: StepType, overrides: Partial<StepDraft> = {}): StepDraft {
  return {
    ...normalizeStepByType(createEmptyStepDraft(0), type),
    ...overrides
  }
}

function getFieldError(_field: keyof StepValidationErrors): string {
  return ''
}

function getTemplateOptions(_step: StepDraft): StepTemplateOption[] {
  return []
}

function mountTypeFields(
  type: StepType,
  overrides: Partial<StepDraft> = {}
): VueWrapper {
  return shallowMount(StepTypeFields, {
    props: {
      step: makeStep(type, overrides),
      allowComponentCall: true,
      getFieldError,
      getStepTemplateOptionsFn: getTemplateOptions
    },
    global: {
      stubs: elementStubs
    }
  })
}

function makeTemplate(id: number, matchStrategy: string, name: string): Template {
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
    createdAt: '',
    updatedAt: '',
    imageLabel: '',
    baselineRevisions: [],
    maskRegions: []
  }
}

describe('shared step fields', (): void => {
  const ordinaryFieldCases: Array<[StepType, string]> = [
    ['wait', '等待时长(ms)'],
    ['click', '定位方式'],
    ['input', '输入方式'],
    ['template_assert', '模板选择'],
    ['ocr_assert', '断言范围'],
    ['component_call', '组件选择'],
    ['navigate', 'URL / 相对路径'],
    ['scroll', '滑动目标'],
    ['long_press', '长按时长(ms)']
  ]

  for (const [type, expectedLabel] of ordinaryFieldCases) {
    it(`renders ${type} fields`, (): void => {
      expect(mountTypeFields(type).text()).toContain(expectedLabel)
    })
  }

  it.each<[LocatorType, string]>([
    ['selector', '选择器'],
    ['visual', '锚点横向比例']
  ])(
    'renders the %s locator fields',
    (locator: LocatorType, expectedLabel: string): void => {
      expect(mountTypeFields('click', { locator }).text()).toContain(expectedLabel)
    }
  )

  it('uses the shared OCR target fields for interaction and selection targets', (): void => {
    const click = mountTypeFields('click', { locator: 'ocr' })
    const select = mountTypeFields('select_option')

    expect(click.findAllComponents(OcrTargetFields)).toHaveLength(1)
    expect(click.findComponent(OcrTargetFields).props('title')).toBe('交互目标')
    expect(select.findAllComponents(OcrTargetFields)).toHaveLength(2)
    expect(
      select.findAllComponents(OcrTargetFields).map(
        (wrapper): string => wrapper.props('title') as string
      )
    ).toEqual(['字段目标', '选项目标'])
  })

  it('marks legacy OCR assertions and keeps selector editing visible', (): void => {
    const wrapper = mountTypeFields('ocr_assert', {
      ocrAssertionScope: 'element_legacy',
      selector: '#result'
    })

    expect(wrapper.text()).toContain('兼容模式')
    expect(wrapper.text()).toContain('兼容选择器')
    expect(wrapper.findComponent(OcrTargetFields).props('showScope')).toBe(false)
  })

  it('reuses OCR target fields for conditional branch metadata', (): void => {
    const branch = makeStep('conditional_branch').conditionalBranches[0]
    branch.ocrTarget.text = '欢迎回来'
    const wrapper = shallowMount(ConditionalBranchMetadataFields, {
      props: {
        branch,
        templateOptions: []
      },
      global: {
        stubs: elementStubs
      }
    })

    const targetFields = wrapper.findComponent(OcrTargetFields)
    expect(targetFields.exists()).toBe(true)
    expect(targetFields.props('target')).toMatchObject({
      text: '欢迎回来',
      scope: 'viewport'
    })
    expect(targetFields.props('showActionPoint')).toBe(false)
  })

  it('keeps conditional branch child types restricted and filters condition templates', (): void => {
    const step = makeStep('conditional_branch')
    step.conditionalBranches[0].conditionType = 'template_visible'
    const wrapper = shallowMount(ConditionalBranchFields, {
      props: {
        step,
        templates: [
          makeTemplate(1, 'template', 'Template A'),
          makeTemplate(2, 'ocr', 'OCR B')
        ],
        getStepTemplateOptionsFn: getTemplateOptions
      },
      global: {
        stubs: elementStubs
      }
    })

    const childFields = wrapper.findComponent(BranchChildStepFields)
    const childTypeOptions = childFields.props('childTypeOptions') as StepTypeOption[]
    const childTypes = childTypeOptions.map((option: StepTypeOption): StepType => option.value)
    const metadataFields = wrapper.findComponent(ConditionalBranchMetadataFields)
    const templateOptions = metadataFields.props('templateOptions') as StepTemplateOption[]

    expect(childTypes).not.toContain('component_call')
    expect(childTypes).not.toContain('conditional_branch')
    expect(childTypes).toContain('select_option')
    expect(childTypes).toHaveLength(9)
    expect(templateOptions.map((option: StepTemplateOption): string => option.label)).toEqual([
      'Template A (#1)'
    ])
  })
})
