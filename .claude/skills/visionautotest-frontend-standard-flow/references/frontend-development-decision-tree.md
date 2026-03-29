# VisionAutoTest 前端开发决策树

## 目录
- 1. 使用方式
- 2. 总入口决策树
- 3. 文件落点决策树
- 4. 领域决策树
- 5. 风险决策树
- 6. 验证决策树
- 7. 当前稳定基线

## 1. 使用方式
- 在开始修改前，先走一遍"总入口决策树"，判断这是契约变更、页面变更、共享能力变更还是执行链路变更。
- 再走"文件落点决策树"，确定代码应该落在 `views`、`components`、`stores`、`api/modules`、`types` 或 `utils`。
- 若任务涉及后端字段、状态流或执行结果展示，再走对应"领域决策树"和"风险决策树"。
- 编码完成后，按"验证决策树"选择最窄验证路径。

## 2. 总入口决策树

### 2.1 先判断是否需要读契约
1. 这个需求是否新增、删除、重命名后端字段？
   - 是：先读 `doc/api/00-API设计总览.md` 和对应业务域 API 文档，再看 `backend/app/api/v1/` 真路由。
   - 否：进入下一问。
2. 这个需求是否改请求路径、查询参数、请求体、状态码或错误码？
   - 是：先改契约映射层，不要先改页面。
   - 否：进入下一问。
3. 这个需求是否只改展示、交互、布局或提示文案？
   - 是：优先从页面/组件层进入。
   - 否：继续判断是否涉及状态与数据流。

### 2.2 再判断是否涉及全局状态
1. 变更是否跨页面共享？
   - 是：优先考虑 `stores`、共享组件或共享 `utils`。
   - 否：优先留在单个页面内部。
2. 变更是否依赖登录态或工作空间态？
   - 是：先检查 `auth.ts`、`workspace.ts`、`router/index.ts`、`api/client.ts`。
   - 否：继续判断业务域。

### 2.3 最后判断业务域
1. 登录、会话、登出、当前用户？ → 进入"认证与空间决策树"。
2. 工作空间、成员、环境、设备？ → 进入"环境与空间决策树"。
3. 模板、基线、忽略区域、媒体上传？ → 进入"模板与媒体决策树"。
4. 用例、步骤、组件、套件？ → 进入"编排与执行入口决策树"。
5. 执行批次、执行详情、轮询、结果聚合？ → 进入"执行详情决策树"。

## 3. 文件落点决策树

### 3.1 改动应该放在哪一层
1. 这是路由级页面编排吗？ → 放 `frontend/src/views`。
2. 这是多个页面复用的视觉块或交互块吗？ → 放 `frontend/src/components`。
3. 这是导航框架、头部、侧边栏、主容器吗？ → 放 `frontend/src/layouts`。
4. 这是跨页面共享状态、持久化状态、全局上下文吗？ → 放 `frontend/src/stores`。
5. 这是请求、DTO 映射、资源读写吗？ → 放 `frontend/src/api/modules`。
6. 这是后端原始结构定义吗？ → 放 `frontend/src/types/backend.ts`。
7. 这是前端消费模型定义吗？ → 放 `frontend/src/types/models.ts`。
8. 这是纯格式化、错误归一化、无 UI 工具函数吗？ → 放 `frontend/src/utils`。

### 3.2 什么情况下不要新建层
- 只在单个页面使用的逻辑，不要先抽 store。
- 只为一个接口做字段转换，不要先抽全局 util。
- 只在一个页面内复用一两次的展示块，不要先抽成过度通用组件。
- 正常 HTTP 请求不要绕开 `frontend/src/api/client.ts`。

## 4. 领域决策树

### 4.1 认证与空间决策树
1. 需求是否改登录/登出行为？ → 先看 `frontend/src/views/LoginView.vue` → 再看 `frontend/src/api/modules/auth.ts` → 再看 `frontend/src/stores/auth.ts`
2. 需求是否改登录后跳转或未登录保护？ → 检查 `frontend/src/router/index.ts`
3. 需求是否改工作空间列表、切换或空工作空间处理？ → 检查 `frontend/src/stores/workspace.ts` → 检查 `frontend/src/components/AppHeader.vue` → 检查 `frontend/src/views/EmptyWorkspaceView.vue`
4. 需求是否受 `X-Workspace-Id` 影响？ → 必查 `frontend/src/api/client.ts`

### 4.2 环境与空间决策树
1. 只是环境/设备列表展示？ → 先改 `frontend/src/views/EnvironmentProfilesView.vue`
2. 需要新增环境或设备字段？ → 先改 `frontend/src/types/backend.ts` → 再改 `frontend/src/api/modules/environments.ts` → 再改 `frontend/src/types/models.ts` → 最后改页面展示
3. 需要做环境/设备增删改？ → 优先扩展 `api/modules/environments.ts`，页面只保留表单编排和反馈

### 4.3 模板与媒体决策树
1. 需求是否只改模板列表/详情展示？ → 先看 `frontend/src/views/TemplatesView.vue`
2. 需求是否改模板字段、基线字段、mask 字段？ → 先改 `frontend/src/types/backend.ts` → 再改 `frontend/src/api/modules/templates.ts` → 再改 `frontend/src/types/models.ts`
3. 需求是否改上传、媒体对象或基线创建？ → 检查 `frontend/src/api/modules/mediaObjects.ts` → 检查 `frontend/src/api/modules/templates.ts`
4. 需求是否改忽略区域编辑体验？ → 优先改 `frontend/src/components/TemplateCanvas.vue`，若只是页面编排，再补 `frontend/src/views/TemplatesView.vue`
5. 需求是否改坐标计算规则？ → 必须保持相对比例坐标，必须保持 0~1 clamp，必须保持最小区域限制，不要改成像素持久化

### 4.4 编排与执行入口决策树
1. 需求是否只改用例列表/详情展示？ → 先看 `frontend/src/views/TestCasesView.vue` → 再看 `frontend/src/api/modules/testCases.ts`
2. 需求是否只改套件详情或套件内用例展示？ → 先看 `frontend/src/views/TestSuitesView.vue` → 再看 `frontend/src/api/modules/testSuites.ts`
3. 需求是否改执行门禁规则？ → 优先改 `frontend/src/views/TestSuitesView.vue` → 同步核对 `doc/联调文档/00-前端联调总览.md`
4. 需求是否发现套件页过重、逻辑继续增长？ → 优先抽局部 composable 或独立业务模块，不要直接把门禁逻辑扩散进 API 层

### 4.5 执行详情决策树
1. 需求是否改执行批次列表？ → 先看 `frontend/src/views/TestRunsView.vue` → 再看 `frontend/src/api/modules/testRuns.ts`
2. 需求是否改执行详情聚合？ → 先看 `frontend/src/api/modules/testRuns.ts` → 再看 `frontend/src/views/RunDetailView.vue`
3. 需求是否新增轮询或实时刷新？ → 先保持在页面层或共享 composable，不要把轮询状态写死进 API 模块
4. 需求是否改 `case-runs` 或 `step-results` 展示结构？ → 保持 `test-runs -> case-runs -> step-results` 主链路不变，保持 `component_call` 展开后按线性步骤展示的兼容性

## 5. 风险决策树

### 5.1 契约风险
1. 字段名来自后端是 `snake_case` 吗？ → 只在 DTO 和 API 映射层保留，页面与前端模型统一用 `camelCase`
2. 后端文档和后端代码不一致吗？ → 以后端真实路由与 schema 为准，再决定是否补文档

### 5.2 数据流风险
1. 这个页面是否做了二次聚合？ → 检查是否又引入 N+1
2. 这个需求会不会让页面额外为列表中的每一项发请求？ → 优先评估是否应推动后端聚合接口

当前高风险聚合点：workspaces.ts、environments.ts、testRuns.ts

### 5.3 交互风险
1. 需求是否涉及模板画布拖拽、缩放、选中态？ → 先自查是否破坏最小区域、边界 clamp、负 ID 草稿区逻辑
2. 需求是否涉及工作空间切换？ → 检查页面是否依赖 `RouterView key` 重建
3. 需求是否涉及全局异常或降级？ → 检查 `main.ts`、`utils/error.ts`、`stores/appError.ts`

### 5.4 体积风险
1. 是否要引入新依赖？ → 先问自己能否复用现有 `Element Plus`、`Tailwind`、原生能力
2. 是否会增加首屏或单页大包？ → 优先懒加载和局部分拆

## 6. 验证决策树

### 6.1 默认验证
- 只要改了前端代码，默认运行：`cd frontend && npm run build`

### 6.2 按改动类型补验证
1. 改登录、空间、路由守卫？ → 手工检查：登录 -> 拉工作空间 -> 跳转正确页面
2. 改模板与画布？ → 手工检查：选模板 -> 新建 mask -> 拖拽/缩放 -> 保存后仍正确回显
3. 改套件执行入口？ → 手工检查：选择套件 -> 门禁提示 -> 创建执行 -> 跳转执行详情
4. 改执行详情？ → 手工检查：打开执行详情 -> case-run 切换 -> step-results 正常显示

### 6.3 自检清单
- 是否把变更放到了正确层？
- 是否先改 DTO，再改 mapping，再改 view？
- 是否补齐 loading、empty、error、disabled、success？
- 是否复用了现有 `ApiError`、`ElMessage`、`StatusTag`、`SectionCard`？
- 是否避免了无关重构？

## 7. 当前稳定基线
- 前端技术栈：`Vue 3 + Vite + TypeScript + Pinia + Element Plus + Tailwind CSS`
- 全局请求入口：`frontend/src/api/client.ts`
- 工作空间上下文核心：`frontend/src/stores/workspace.ts`
- 模板复杂热点：`frontend/src/views/TemplatesView.vue` + `frontend/src/components/TemplateCanvas.vue`
- 执行入口复杂热点：`frontend/src/views/TestSuitesView.vue`
- 执行详情复杂热点：`frontend/src/views/RunDetailView.vue` + `frontend/src/api/modules/testRuns.ts`
- 当前最稳定联调闭环：登录 → 工作空间切换 → 模板与 mask 管理 → 套件执行门禁 → 创建执行 → 查看执行详情
