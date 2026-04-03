import type { ExecutionReadinessIssue } from '@/types/models'

const readinessSuggestionMap: Record<string, string> = {
  ENVIRONMENT_PROFILE_REQUIRED: '前往环境配置页，新建并启用至少一个环境档案。',
  TEST_SUITE_REQUIRED: '前往套件管理页，创建并激活至少一个可执行套件。',
  TEST_SUITE_NOT_ACTIVE: '将当前套件状态切换为 active，再重新触发执行。',
  TEST_SUITE_EMPTY: '先为当前套件编排至少一个可执行用例。',
  PUBLISHED_VERSION_REQUIRED: '将当前资源发布到可执行状态，再重新检查执行就绪度。',
  BASELINE_REVISION_REQUIRED: '为当前模板补充并设置一个当前基准版本。',
  STEP_CONFIGURATION_INVALID: '检查当前步骤配置，补齐必填字段并确认断言策略匹配。',
  TEMPLATE_NOT_FOUND: '重新选择有效模板，或修复已失效的模板引用关系。',
  TEST_CASE_NOT_FOUND: '重新编排有效测试用例，移除失效引用。',
  READINESS_LOAD_FAILED: '稍后重试；若持续失败，请先检查接口服务是否可用。'
}

const readinessActionLabelMap: Record<string, string> = {
  ENVIRONMENT_PROFILE_REQUIRED: '去配置环境',
  TEST_SUITE_REQUIRED: '去新建套件',
  TEST_SUITE_NOT_ACTIVE: '去激活套件',
  TEST_SUITE_EMPTY: '去编排套件',
  PUBLISHED_VERSION_REQUIRED: '去处理发布',
  BASELINE_REVISION_REQUIRED: '去补基准',
  STEP_CONFIGURATION_INVALID: '去检查步骤',
  TEMPLATE_NOT_FOUND: '去修复模板',
  TEST_CASE_NOT_FOUND: '去修复用例',
  READINESS_LOAD_FAILED: '稍后重试'
}

export function getReadinessSuggestion(issue: ExecutionReadinessIssue) {
  return readinessSuggestionMap[issue.code] ?? '根据阻塞提示修复对应资源后，再重新检查执行就绪度。'
}

export function getReadinessActionLabel(issue: ExecutionReadinessIssue) {
  return readinessActionLabelMap[issue.code] ?? '去处理'
}

export function canResolveReadinessByNavigation(issue: ExecutionReadinessIssue) {
  return issue.code !== 'READINESS_LOAD_FAILED'
}
