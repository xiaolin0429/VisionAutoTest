const statusLabelMap: Record<string, string> = {
  active: '启用',
  inactive: '停用',
  archived: '归档',
  draft: '草稿',
  published: '已发布',
  queued: '排队中',
  running: '执行中',
  cancelling: '取消中',
  cancelled: '已取消',
  passed: '通过',
  failed: '失败',
  partial_failed: '部分失败',
  error: '异常',
  pending: '待执行',
  skipped: '已跳过'
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

export function formatStatusLabel(status: string) {
  return statusLabelMap[status] ?? status
}

export function formatRatio(value: number) {
  return `${Math.round(value * 100)}%`
}
