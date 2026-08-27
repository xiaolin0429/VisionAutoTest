import type { App, Component, Plugin } from 'vue'
import {
  Collection,
  DataBoard,
  EditPen,
  Histogram,
  Picture,
  Setting
} from '@element-plus/icons-vue'
import {
  ElCheckbox,
  ElCol,
  ElAvatar,
  ElButton,
  ElButtonGroup,
  ElColorPicker,
  ElDialog,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLoadingDirective,
  ElMenu,
  ElMenuItem,
  ElPopover,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElScrollbar,
  ElSelect,
  ElOption,
  ElSlider,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTabPane,
  ElTag,
  ElTimeline,
  ElTimelineItem,
  ElTooltip
} from 'element-plus'

import 'element-plus/es/components/avatar/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/button-group/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/col/style/css'
import 'element-plus/es/components/color-picker/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/drawer/style/css'
import 'element-plus/es/components/dropdown/style/css'
import 'element-plus/es/components/dropdown-item/style/css'
import 'element-plus/es/components/dropdown-menu/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/icon/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/input-number/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/menu/style/css'
import 'element-plus/es/components/menu-item/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/popover/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/row/style/css'
import 'element-plus/es/components/scrollbar/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/slider/style/css'
import 'element-plus/es/components/switch/style/css'
import 'element-plus/es/components/tab-pane/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/table-column/style/css'
import 'element-plus/es/components/tabs/style/css'
import 'element-plus/es/components/tag/style/css'
import 'element-plus/es/components/timeline/style/css'
import 'element-plus/es/components/timeline-item/style/css'
import 'element-plus/es/components/tooltip/style/css'

const components: Array<Plugin | Component> = [
  ElAvatar,
  ElButton,
  ElButtonGroup,
  ElCheckbox,
  ElCol,
  ElColorPicker,
  ElDialog,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMenu,
  ElMenuItem,
  ElPopover,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElScrollbar,
  ElSelect,
  ElOption,
  ElSlider,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTabPane,
  ElTag,
  ElTimeline,
  ElTimelineItem,
  ElTooltip
]

const icons = {
  Collection,
  DataBoard,
  EditPen,
  Histogram,
  Picture,
  Setting
}

export function installElementPlus(app: App) {
  components.forEach((component) => {
    const componentWithInstall = component as Plugin & { name?: string }

    if (
      componentWithInstall.name &&
      app.component(componentWithInstall.name)
    ) {
      return
    }

    if (typeof componentWithInstall.install === 'function') {
      app.use(componentWithInstall)
    }

    if (
      componentWithInstall.name &&
      !app.component(componentWithInstall.name)
    ) {
      app.component(componentWithInstall.name, component as Component)
    }
  })

  Object.entries(icons).forEach(([name, component]) => {
    app.component(name, component)
  })

  app.directive('loading', ElLoadingDirective)
}
