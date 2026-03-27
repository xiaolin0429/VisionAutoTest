# 环境与设备配置 API

## 1. 模块范围

本模块负责工作空间下的环境档案、环境变量和设备预设配置。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `environment-profiles` | 环境档案 |
| `environment-variables` | 环境变量 |
| `device-profiles` | 设备预设 |

## 3. 接口定义

### 3.1 查询环境档案列表

- 方法：`GET`
- 路径：`/api/v1/environment-profiles`
- 必填请求头：`X-Workspace-Id`

### 3.2 创建环境档案

- 方法：`POST`
- 路径：`/api/v1/environment-profiles`

### 3.3 查询环境档案详情

- 方法：`GET`
- 路径：`/api/v1/environment-profiles/{environment_profile_id}`

### 3.4 更新环境档案

- 方法：`PATCH`
- 路径：`/api/v1/environment-profiles/{environment_profile_id}`

### 3.5 删除环境档案

- 方法：`DELETE`
- 路径：`/api/v1/environment-profiles/{environment_profile_id}`

### 3.6 查询环境变量列表

- 方法：`GET`
- 路径：`/api/v1/environment-profiles/{environment_profile_id}/variables`

### 3.7 新增环境变量

- 方法：`POST`
- 路径：`/api/v1/environment-profiles/{environment_profile_id}/variables`

### 3.8 更新环境变量

- 方法：`PATCH`
- 路径：`/api/v1/environment-variables/{environment_variable_id}`

### 3.9 删除环境变量

- 方法：`DELETE`
- 路径：`/api/v1/environment-variables/{environment_variable_id}`

### 3.10 查询设备预设列表

- 方法：`GET`
- 路径：`/api/v1/device-profiles`

### 3.11 创建设备预设

- 方法：`POST`
- 路径：`/api/v1/device-profiles`

### 3.12 更新设备预设

- 方法：`PATCH`
- 路径：`/api/v1/device-profiles/{device_profile_id}`

## 4. 业务规则

- 环境档案名在同一工作空间内唯一。
- 环境变量键名在同一环境档案内唯一。
- 敏感变量必须支持加密存储，并在接口层进行脱敏返回。
- 设备预设采用工作空间级管理，可沉淀公共设备模板。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `ENVIRONMENT_PROFILE_NOT_FOUND` | 环境档案不存在 |
| `ENVIRONMENT_PROFILE_NAME_EXISTS` | 档案名称重复 |
| `ENVIRONMENT_VARIABLE_KEY_EXISTS` | 变量键重复 |
| `DEVICE_PROFILE_NOT_FOUND` | 设备预设不存在 |
