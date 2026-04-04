# 模板与基准资产 API

## 1. 模块范围

本模块负责视觉模板、基准版本、忽略区域和模板侧资产引用。  
媒体对象的通用生命周期已拆分到 [09-媒体对象 API](./09-媒体对象API.md)，避免本篇同时承载上传、引用、生命周期三类语义。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `templates` | 视觉模板 |
| `baseline-revisions` | 基准版本 |
| `ocr-results` | 模板基准图 OCR 结果快照 |
| `preview-images` | 模板基准图 Mask 预览结果 |
| `mask-regions` | 忽略区域 |

## 3. 接口定义

### 3.1 查询模板列表

- 方法：`GET`
- 路径：`/api/v1/templates`

查询参数：

- `page`
- `page_size`
- `template_type`
- `status`
- `keyword`

### 3.2 创建模板

- 方法：`POST`
- 路径：`/api/v1/templates`

说明：

- 请求体中必须包含 `original_media_object_id`

### 3.3 查询模板详情

- 方法：`GET`
- 路径：`/api/v1/templates/{template_id}`

### 3.4 更新模板

- 方法：`PATCH`
- 路径：`/api/v1/templates/{template_id}`

### 3.5 查询模板基准版本

- 方法：`GET`
- 路径：`/api/v1/templates/{template_id}/baseline-revisions`

### 3.6 新增模板基准版本

- 方法：`POST`
- 路径：`/api/v1/templates/{template_id}/baseline-revisions`

请求体：

```json
{
  "media_object_id": 7002,
  "source_type": "adopted_from_failure",
  "source_report_id": 8001,
  "source_case_run_id": 6002,
  "source_step_result_id": 9102,
  "remark": "adopt latest accepted screenshot",
  "is_current": true
}
```

### 3.7 查询忽略区域列表

- 方法：`GET`
- 路径：`/api/v1/templates/{template_id}/mask-regions`

### 3.8 查询模板基准版本 OCR 结果

- 方法：`GET`
- 路径：`/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results`

说明：

- 返回当前 `template_id + baseline_revision_id` 维度下最新一次 OCR 快照。
- 若该基准版本尚未生成过 OCR 结果，则返回 `200`，并通过 `status=not_generated` 表示未生成态。

### 3.9 触发模板基准版本 OCR 分析

- 方法：`POST`
- 路径：`/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results`

说明：

- 同步执行单张基准图 OCR 分析。
- 同一 `template_id + baseline_revision_id` 仅保留一份最新 OCR 快照；重复触发时覆盖更新，不新增历史版本。
- 即使 OCR 分析失败，也会写入失败态快照，便于后续查询失败信息。

建议返回字段至少包含：

- `template_id`
- `baseline_revision_id`
- `source_media_object_id`
- `status`
- `image_width`
- `image_height`
- `engine_name`
- `blocks`
- `error_code`
- `error_message`

其中每个 `blocks[]` 至少包含：

- `order_no`
- `text`
- `confidence`
- `polygon_points`
- `pixel_rect`
- `ratio_rect`

### 3.10 创建模板基准版本预览图

- 方法：`POST`
- 路径：`/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images`

请求体：

```json
{
  "mask_regions": [
    {
      "name": "dynamic_title",
      "x_ratio": 0.12,
      "y_ratio": 0.08,
      "width_ratio": 0.34,
      "height_ratio": 0.10,
      "sort_order": 1
    }
  ]
}
```

说明：

- `mask_regions` 可选；未传时使用模板当前已持久化的 `mask-regions`。
- 传入 `mask_regions` 时仅用于本次预览生成，不会写回模板正式忽略区域。
- 响应固定返回 `overlay` 与 `processed` 两张预览图对应的媒体对象及稳定访问路径。
- 其中 `processed` 预览用于帮助用户确认忽略区域覆盖范围，当前会将忽略区域做弱侵入的马赛克化展示，而非纯黑遮挡；执行链路内部的真实忽略逻辑不受该预览样式影响。

### 3.11 新增忽略区域

- 方法：`POST`
- 路径：`/api/v1/templates/{template_id}/mask-regions`

请求体：

```json
{
  "region_name": "header_banner",
  "x_ratio": 0.12,
  "y_ratio": 0.08,
  "width_ratio": 0.56,
  "height_ratio": 0.14
}
```

### 3.12 更新忽略区域

- 方法：`PATCH`
- 路径：`/api/v1/mask-regions/{mask_region_id}`

### 3.13 删除忽略区域

- 方法：`DELETE`
- 路径：`/api/v1/mask-regions/{mask_region_id}`

## 4. 业务规则

- 模板与工作空间强绑定。
- 当前版本 `match_strategy` 只支持 `template` 与 `ocr`。
- 当前版本模板状态建议使用 `draft/published/archived`，其中只有 `published` 模板可进入执行链路。
- 同一模板下只允许有一个 `is_current=true` 的基准版本。
- `baseline-revisions.source_type` 当前固定收口为 `manual/uploaded/adopted_from_failure`。
- 当 `source_type=adopted_from_failure` 时，`source_step_result_id` 必填；若同时传 `source_case_run_id/source_report_id`，必须与该步骤结果所属执行链路一致。
- 失败证据采纳当前仅允许使用步骤结果中的 `actual_media_object_id` 作为新基准，不允许直接采纳 `diff_media_object_id`。
- 失败证据采纳必须能反向关联到报告、用例执行实例和步骤结果，供前端进入“确认变更合法 -> 更新基准”的闭环。
- 忽略区域坐标统一使用相对比例，不允许直接持久化像素值作为标准坐标。
- 模板创建时必须绑定至少一个原始媒体对象。
- OCR 结果按 `template_id + baseline_revision_id` 绑定，只保留一份最新快照；切换基准版本时不得混用其他基准版本的 OCR 结果。
- OCR 结果中的 `ratio_rect` 必须可直接映射为模板忽略区域的比例坐标，前端不需要单独请求坐标转换接口。
- 预览图始终基于显式 `baseline_revision_id` 生成，不允许隐式回退到模板当前基准版本。
- 预览图通过媒体对象模型稳定访问，前端不需要自行执行复杂图像叠加或蒙版计算。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `TEMPLATE_NOT_FOUND` | 模板不存在 |
| `TEMPLATE_MATCH_STRATEGY_UNSUPPORTED` | 当前版本不支持该模板匹配策略 |
| `TEMPLATE_STATUS_INVALID` | 模板状态非法 |
| `BASELINE_REVISION_CONFLICT` | 当前基准版本冲突 |
| `BASELINE_SOURCE_TYPE_INVALID` | 基准版本来源类型非法 |
| `BASELINE_ADOPTION_INVALID` | 失败证据采纳参数非法 |
| `BASELINE_ADOPTION_MISMATCH` | 失败证据与模板基准链路不匹配 |
| `BASELINE_REVISION_NOT_FOUND` | 基准版本不存在或不属于当前模板 |
| `TEMPLATE_OCR_RESULT_NOT_FOUND` | 当前模板基准版本尚未生成 OCR 结果 |
| `TEMPLATE_OCR_ANALYSIS_FAILED` | OCR 分析执行失败 |
| `TEMPLATE_PREVIEW_GENERATION_FAILED` | Mask 预览图生成失败 |
| `MASK_REGION_OUT_OF_RANGE` | 忽略区域坐标越界 |
| `MEDIA_OBJECT_NOT_FOUND` | 媒体对象不存在 |
