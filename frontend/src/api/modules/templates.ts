import { requestData, requestPage } from '@/api/client'
import type {
  BaselineRevisionReadDTO,
  MaskRegionReadDTO,
  TemplateReadDTO
} from '@/types/backend'
import type { Template } from '@/types/models'

function mapMaskRegions(items: MaskRegionReadDTO[]) {
  return items.map((item) => ({
    id: item.id,
    name: item.region_name,
    xRatio: Number(item.x_ratio),
    yRatio: Number(item.y_ratio),
    widthRatio: Number(item.width_ratio),
    heightRatio: Number(item.height_ratio),
    sortOrder: item.sort_order
  }))
}

function resolveBaselineVersion(
  currentBaselineRevisionId: number | null,
  revisions: BaselineRevisionReadDTO[]
) {
  if (!currentBaselineRevisionId) {
    return '未设置'
  }

  const currentRevision = revisions.find((item) => item.id === currentBaselineRevisionId)
  if (!currentRevision) {
    return `#${currentBaselineRevisionId}`
  }

  return `v${currentRevision.revision_no}`
}

function mapTemplateSummary(item: TemplateReadDTO): Template {
  return {
    id: item.id,
    code: item.template_code,
    name: item.template_name,
    templateType: item.template_type,
    matchStrategy: item.match_strategy,
    thresholdValue: Number(item.threshold_value),
    status: item.status,
    currentBaselineRevisionId: item.current_baseline_revision_id,
    baselineVersion: item.current_baseline_revision_id
      ? `#${item.current_baseline_revision_id}`
      : '未设置',
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    imageLabel: `${item.match_strategy} / 阈值 ${Number(item.threshold_value).toFixed(2)}`,
    maskRegions: []
  }
}

export async function listTemplates(): Promise<Template[]> {
  const response = await requestPage<TemplateReadDTO>({
    method: 'get',
    url: '/templates',
    params: {
      page: 1,
      page_size: 100
    }
  })

  return response.data.map(mapTemplateSummary)
}

export async function getTemplateDetail(templateId: number): Promise<Template> {
  const [template, baselineRevisions, maskRegions] = await Promise.all([
    requestData<TemplateReadDTO>({
      method: 'get',
      url: `/templates/${templateId}`
    }),
    requestData<BaselineRevisionReadDTO[]>({
      method: 'get',
      url: `/templates/${templateId}/baseline-revisions`
    }),
    requestData<MaskRegionReadDTO[]>({
      method: 'get',
      url: `/templates/${templateId}/mask-regions`
    })
  ])

  return {
    ...mapTemplateSummary(template),
    baselineVersion: resolveBaselineVersion(
      template.current_baseline_revision_id,
      baselineRevisions
    ),
    imageLabel: `${template.match_strategy} / 阈值 ${Number(template.threshold_value).toFixed(2)}`,
    maskRegions: mapMaskRegions(maskRegions)
  }
}
