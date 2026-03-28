import type { App, Plugin } from 'vue'
import {
  Collection,
  DataBoard,
  EditPen,
  Histogram,
  Picture,
  Setting
} from '@element-plus/icons-vue'
import {
  ElAvatar,
  ElButton,
  ElEmpty,
  ElIcon,
  ElInput,
  ElLoadingDirective,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTimeline,
  ElTimelineItem
} from 'element-plus'

import 'element-plus/es/components/avatar/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/icon/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/menu/style/css'
import 'element-plus/es/components/menu-item/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/table-column/style/css'
import 'element-plus/es/components/tag/style/css'
import 'element-plus/es/components/timeline/style/css'
import 'element-plus/es/components/timeline-item/style/css'

const components: Plugin[] = [
  ElAvatar,
  ElButton,
  ElEmpty,
  ElIcon,
  ElInput,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTimeline,
  ElTimelineItem
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
    app.use(component)
  })

  Object.entries(icons).forEach(([name, component]) => {
    app.component(name, component)
  })

  app.directive('loading', ElLoadingDirective)
}
