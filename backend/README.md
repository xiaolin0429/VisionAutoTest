# VisionAutoTest Backend MVP

服务端 MVP 骨架，基于 `FastAPI + SQLAlchemy 2.x`，对应仓库中的 MVP、API 与数据库设计文档。

## 当前骨架覆盖

- 身份与会话
- 工作空间与成员
- 环境档案、环境变量、设备预设
- 媒体对象、模板、基准版本、忽略区域
- 测试组件、测试用例、测试套件
- 异步执行批次、用例执行实例、步骤结果、报告
- 基于 Playwright 的浏览器截图闭环（首批支持 `wait`、`click`、`input`）

## 本地启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
uvicorn app.main:app --reload
```

默认使用本地 SQLite：

- 数据库文件：`backend/.data/visionautotest.db`
- 媒体目录：`backend/.data/media`

执行链路补充说明：

- 当前 MVP 首批真实浏览器执行支持 `wait`、`click`、`input`
- 用例执行完成后会产出真实截图，并写入 `media-objects` 与 `report-artifacts`
- 当前尚未接入 `OpenCV` / `OCR` 的视觉断言闭环，模板比对与 OCR 断言留待下一阶段实现

初始化时会自动创建一个默认管理员：

- 用户名：`admin`
- 密码：`admin123456`

## 后续建议

- 接入 Alembic 迁移脚本
- 将当前示例令牌替换为 JWT
- 将环境变量“伪加密”替换为正式密钥管理方案
- 将执行 Worker 从进程内任务平滑升级为 `Celery + Redis`
