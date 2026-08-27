import { createApp, defineComponent, type App } from 'vue'
import { describe, expect, it } from 'vitest'

import { installElementPlus } from './element'

const templateComponentNames = [
  'ElAvatar',
  'ElButton',
  'ElButtonGroup',
  'ElCheckbox',
  'ElColorPicker',
  'ElDialog',
  'ElDrawer',
  'ElDropdown',
  'ElDropdownItem',
  'ElDropdownMenu',
  'ElEmpty',
  'ElForm',
  'ElFormItem',
  'ElIcon',
  'ElInput',
  'ElInputNumber',
  'ElMenu',
  'ElMenuItem',
  'ElOption',
  'ElPopover',
  'ElRadioButton',
  'ElRadioGroup',
  'ElScrollbar',
  'ElSelect',
  'ElSlider',
  'ElSwitch',
  'ElTabPane',
  'ElTable',
  'ElTableColumn',
  'ElTabs',
  'ElTag',
  'ElTimeline',
  'ElTimelineItem',
  'ElTooltip'
] as const

function createInstalledApp(): App {
  const app = createApp(defineComponent({ template: '<div />' }))
  installElementPlus(app)
  return app
}

describe('Element Plus registration', (): void => {
  it('resolves every el-* component used by frontend templates', (): void => {
    const app = createInstalledApp()

    templateComponentNames.forEach((name: string): void => {
      expect(app.component(name), `${name} should be registered`).toBeTruthy()
    })
  })

  it('keeps shared shell icons globally resolvable', (): void => {
    const app = createInstalledApp()

    for (const name of [
      'Collection',
      'DataBoard',
      'EditPen',
      'Histogram',
      'Picture',
      'Setting'
    ]) {
      expect(app.component(name), `${name} should be registered`).toBeTruthy()
    }
  })
})
