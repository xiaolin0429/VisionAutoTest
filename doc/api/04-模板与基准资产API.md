# 模板与基准资产 API

## 1. 模块范围

本模块负责视觉模板、基准版本、忽略区域和模板侧资产引用。  
媒体对象的通用生命周期已拆分到 [09-媒体对象 API](./09-媒体对象API.md)，避免本篇同时承载上传、引用、生命周期三类语义。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `templates` | 视觉模板 |
| `baseline-revisions` | 基准版本 |
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

### 3.8 新增忽略区域

- 方法：`POST`
- 路径：`/api/v1/templates/{template_id}/mask-regions`

请求体：

```json
{
  "name": "header_banner",
  "x_ratio": 0.12,
  "y_ratio": 0.08,
  "width_ratio": 0.56,
  "height_ratio": 0.14
}
```

### 3.9 更新忽略区域

- 方法：`PATCH`
- 路径：`/api/v1/mask-regions/{mask_region_id}`

### 3.10 删除忽略区域

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
| `MASK_REGION_OUT_OF_RANGE` | 忽略区域坐标越界 |
| `MEDIA_OBJECT_NOT_FOUND` | 媒体对象不存在 |
