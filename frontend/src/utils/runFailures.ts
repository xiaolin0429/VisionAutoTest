import type { CaseRun, RunDetail, StepResult, TestRun } from '@/types/models'

export function isAttentionRunStatus(status: string) {
  return status === 'failed' || status === 'partial_failed' || status === 'error'
}

export function buildRunRepairQuery(testCaseId: number) {
  return { testCaseId: String(testCaseId) }
}

export function buildResourceRepairTarget(step: StepResult | null, fallbackTestCaseId: number) {
  if (!step || !step.repairRoutePath || !step.repairResourceType || step.repairResourceId === null) {
    return {
      path: '/cases',
      query: buildRunRepairQuery(fallbackTestCaseId),
      label: '去修复测试用例'
    }
  }

  if (step.repairResourceType === 'template') {
    const focus =
      step.type === 'template_assert' || step.type === 'ocr_assert' ? 'workbench' : 'baseline'
    return {
      path: '/templates',
      query: {
        templateId: String(step.repairResourceId),
        stepNo: step.repairStepNo ? String(step.repairStepNo) : undefined,
        focus
      },
      label: '去修复模板'
    }
  }
  if (step.repairResourceType === 'component') {
    return {
      path: '/components',
      query: {
        componentId: String(step.repairResourceId),
        stepNo: step.repairStepNo ? String(step.repairStepNo) : undefined
      },
      label: '去修复组件'
    }
  }

  return {
    path: '/cases',
    query: {
      testCaseId: String(step.repairResourceId),
      stepNo: step.repairStepNo ? String(step.repairStepNo) : undefined
    },
    label: '去修复测试用例'
  }
}

export function getPrimaryRepairStep(caseRun: CaseRun | null): StepResult | null {
  if (!caseRun) {
    return null
  }

  return caseRun.steps.find((item) => item.status === 'failed' || item.status === 'error') ?? null
}

export function getPrimaryFailedCaseRun(detail: RunDetail | null): CaseRun | null {
  if (!detail) {
    return null
  }

  return detail.caseRuns.find((item) => item.status === 'failed' || item.status === 'error') ?? null
}

export function resolveRunRepairTarget(detail: RunDetail | null) {
  const failedCaseRun = getPrimaryFailedCaseRun(detail)
  if (!failedCaseRun) {
    return null
  }

  const repairStep = getPrimaryRepairStep(failedCaseRun)
  const repairTarget = buildResourceRepairTarget(repairStep, failedCaseRun.testCaseId)
  return {
    ...repairTarget,
    caseRunName: failedCaseRun.name,
    failureSummary: failedCaseRun.failureSummary
  }
}

export function getRunFailureSuggestion(run: TestRun) {
  if (run.status === 'failed') {
    return '查看失败用例详情，并回到对应测试用例检查断言与步骤配置。'
  }
  if (run.status === 'partial_failed') {
    return '优先定位失败用例，再逐步检查模板基准、组件发布状态与步骤配置。'
  }
  if (run.status === 'error') {
    return '检查执行报告中的失败摘要，并优先回到失败用例修复配置问题。'
  }
  return '当前执行状态无需额外修复动作。'
}
