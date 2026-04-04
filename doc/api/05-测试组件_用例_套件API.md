# 测试组件、用例与套件 API

## 1. 模块范围

本模块负责测试编排域，包括公共组件、测试用例、步骤定义和测试套件。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `components` | 公共组件 |
| `test-cases` | 测试用例 |
| `test-suites` | 测试套件 |
| `steps` | 步骤明细 |

## 3. 接口定义

### 3.1 查询组件列表

- 方法：`GET`
- 路径：`/api/v1/components`

### 3.2 创建组件

- 方法：`POST`
- 路径：`/api/v1/components`

### 3.3 查询组件详情

- 方法：`GET`
- 路径：`/api/v1/components/{component_id}`

### 3.4 更新组件

- 方法：`PATCH`
- 路径：`/api/v1/components/{component_id}`

### 3.5 查询组件步骤

- 方法：`GET`
- 路径：`/api/v1/components/{component_id}/steps`

### 3.6 全量替换组件步骤

- 方法：`PUT`
- 路径：`/api/v1/components/{component_id}/steps`

### 3.7 查询用例列表

- 方法：`GET`
- 路径：`/api/v1/test-cases`

### 3.8 创建用例

- 方法：`POST`
- 路径：`/api/v1/test-cases`

### 3.9 查询用例详情

- 方法：`GET`
- 路径：`/api/v1/test-cases/{test_case_id}`

### 3.10 更新用例

- 方法：`PATCH`
- 路径：`/api/v1/test-cases/{test_case_id}`

### 3.11 查询用例步骤

- 方法：`GET`
- 路径：`/api/v1/test-cases/{test_case_id}/steps`

### 3.12 全量替换用例步骤

- 方法：`PUT`
- 路径：`/api/v1/test-cases/{test_case_id}/steps`

### 3.13 克隆用例

- 方法：`POST`
- 路径：`/api/v1/test-cases/{test_case_id}/clone`
- 说明：深拷贝目标用例的基础信息与全部步骤，生成新用例。新用例 `case_code` 为 `{原编码}_copy_{时间戳}`，状态强制为 `draft`。
- 响应：`201`，返回新用例的 `TestCaseRead`。

### 3.14 查询套件列表

- 方法：`GET`
- 路径：`/api/v1/test-suites`

### 3.15 创建套件

- 方法：`POST`
- 路径：`/api/v1/test-suites`

### 3.16 查询套件详情

- 方法：`GET`
- 路径：`/api/v1/test-suites/{test_suite_id}`

### 3.17 更新套件

- 方法：`PATCH`
- 路径：`/api/v1/test-suites/{test_suite_id}`

### 3.18 查询套件用例集合

- 方法：`GET`
- 路径：`/api/v1/test-suites/{test_suite_id}/cases`

### 3.19 全量替换套件用例集合

- 方法：`PUT`
- 路径：`/api/v1/test-suites/{test_suite_id}/cases`

### 3.20 查询套件执行就绪状态

- 方法：`GET`
- 路径：`/api/v1/test-suites/{test_suite_id}/execution-readiness`

说明：

- 返回指定套件是否满足创建 `test-runs` 的前置条件。
- 阻塞项需落到具体资源或步骤配置问题，供前端直接提示修复。

## 4. 业务规则

- 步骤顺序必须连续，`step_no` 从 1 开始。
- 当步骤类型为 `component_call` 时，必须显式传入 `component_id`。
- 组件和用例状态统一采用 `draft/published/archived`；执行时只能引用 `published` 版本。
- 套件中的用例顺序必须可控，用于稳定回放；套件本身采用 `draft/active/archived` 状态流转。
- 步骤中的变量占位符统一采用 `{{ variable_name }}` 语法。
- MVP 首批真实浏览器执行支持以下步骤载荷约定：
  - `wait`：`payload_json.ms`
  - `click`：`payload_json.selector`（默认）或 OCR 定位模式
  - `input`：`payload_json.selector`（默认）或 OCR 定位模式、`payload_json.text`，可选 `payload_json.input_mode`
  - `navigate`：`payload_json.url`、可选 `payload_json.wait_until`
  - `scroll`：`payload_json.target`、可选 `payload_json.selector`（默认）或 OCR 定位模式、`payload_json.direction`、`payload_json.distance`、可选 `payload_json.behavior`
  - `long_press`：`payload_json.selector`（默认）或 OCR 定位模式、`payload_json.duration_ms`、可选 `payload_json.button`
  - `template_assert`：`template_id`、可选 `payload_json.threshold`
  - `ocr_assert`：`payload_json.selector`、`payload_json.expected_text`、可选 `payload_json.match_mode`、`payload_json.case_sensitive`
- 交互步骤（`click`、`input`、`scroll`（target=element）、`long_press`）支持两种元素定位模式，通过 `payload_json.locator` 切换：
  - `selector`（默认）：基于 CSS 选择器定位，需提供 `payload_json.selector`。
  - `ocr`：基于 OCR 文字识别定位，需提供 `payload_json.ocr_text`（目标文字）；可选 `payload_json.ocr_match_mode`（`exact` 或 `contains`，默认 `contains`）、`payload_json.ocr_case_sensitive`（布尔，默认 `false`）、`payload_json.ocr_occurrence`（正整数，默认 `1`，表示匹配第 N 个结果）。
  - OCR 定位模式下执行引擎会先对当前页面截图做 OCR 识别，找到匹配文字的坐标后在该坐标执行操作。
- `input` 步骤支持通用输入策略，通过 `payload_json.input_mode` 切换：
  - `fill`（默认）：适合普通输入框；selector 定位时优先使用元素填充，OCR 定位时在目标位置聚焦后直接输入文本。
  - `type`：适合需要键盘事件驱动的输入组件；聚焦目标后按字符逐位输入。
  - `otp`：适合验证码、PIN 码等多格输入组件；聚焦目标后按字符逐位输入。可选 `payload_json.otp_length`（正整数，验证码长度）与 `payload_json.per_char_delay_ms`（非负数，逐字符延迟，默认 `80`）。
- `component_call` 为编排步骤，不直接映射浏览器动作；执行时会按组件步骤明细展开成真实执行序列。
- 当前组件展开只支持一层复用，不支持组件内部继续嵌套组件调用。
- `template_assert` 仅允许引用当前工作空间下存在已生效基准版本、且 `match_strategy=template` 的模板。
- `ocr_assert` 默认直接对页面元素截图做 OCR 断言；若显式传入 `template_id`，则该模板必须属于当前工作空间且 `match_strategy=ocr`。
- 断言不通过记为 `failed`，依赖缺失、载荷非法、OCR/视觉引擎异常记为 `error`。
- 套件执行就绪检查需要提前暴露以下阻塞项：套件为空、套件未激活、无可用环境、未发布用例、未发布组件、未发布模板、模板缺少当前基准、步骤配置不兼容。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `COMPONENT_NOT_FOUND` | 组件不存在 |
| `TEST_CASE_NOT_FOUND` | 用例不存在 |
| `TEST_SUITE_NOT_FOUND` | 套件不存在 |
| `STEP_SEQUENCE_INVALID` | 步骤顺序非法 |
| `STEP_CONFIGURATION_INVALID` | 步骤配置与执行要求不兼容 |
| `SUITE_CASE_SEQUENCE_INVALID` | 套件用例顺序非法 |
| `PUBLISHED_VERSION_REQUIRED` | 执行引用了未发布对象 |
