# 媒体对象 API

## 1. 模块范围

本模块负责上传后的媒体对象元数据、生命周期状态和引用约束。  
模板、基准版本、执行证据链都通过 `media-objects` 复用该资源，避免在各业务文档中重复描述。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `media-objects` | 媒体对象 |

## 3. 接口定义

### 3.1 创建媒体对象

- 方法：`POST`
- 路径：`/api/v1/media-objects`
- 请求类型：`multipart/form-data`

表单字段：

- `file`：上传文件
- `usage`：用途，如 `template_source`、`baseline`、`artifact`
- `remark`：可选备注

### 3.2 查询媒体对象详情

- 方法：`GET`
- 路径：`/api/v1/media-objects/{media_object_id}`

### 3.3 查询媒体对象内容

- 方法：`GET`
- 路径：`/api/v1/media-objects/{media_object_id}/content`

### 3.4 查询媒体对象列表

- 方法：`GET`
- 路径：`/api/v1/media-objects`

查询参数：

- `usage`
- `status`
- `page`
- `page_size`

### 3.5 更新媒体对象状态

- 方法：`PATCH`
- 路径：`/api/v1/media-objects/{media_object_id}`

允许更新字段：

- `status`
- `remark`

状态流转建议：

- `active -> archived`
- `active -> deleted`
- `archived -> active`

### 3.6 查询媒体对象引用关系

- 方法：`GET`
- 路径：`/api/v1/media-objects/{media_object_id}/references`

## 4. 业务规则

- 媒体对象内容一经创建不可原地修改；如文件内容发生变化，必须创建新的媒体对象。
- 逻辑删除前必须校验引用关系；若仍被模板、基准版本、报告证据链引用，不允许删除。
- `usage` 仅用于归类和检索，不作为权限控制依据。
- 当前稳定访问入口为 `/api/v1/media-objects/{media_object_id}/content`，其他业务资源返回的 `artifact_url` 应指向该路径或其未来等价替代。
- 后续即使底层切换到对象存储，对前端暴露的媒体访问模型也应保持稳定，不要求前端感知底层对象键。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `MEDIA_OBJECT_NOT_FOUND` | 媒体对象不存在 |
| `MEDIA_OBJECT_UPLOAD_INVALID` | 上传内容非法 |
| `MEDIA_OBJECT_STATUS_CONFLICT` | 状态流转非法 |
| `MEDIA_OBJECT_REFERENCE_CONFLICT` | 存在业务引用，禁止删除 |
