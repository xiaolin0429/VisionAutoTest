import { requestData, requestPage, requestVoid } from '@/api/client'
import type {
  BaselineRevisionReadDTO,
  MaskRegionReadDTO,
  TemplateReadDTO
} from '@/types/backend'
import type {
  BaselineRevision,
  MaskRegion,
  Template,
  TemplateCreatePayload,
  TemplateMaskCreatePayload,
  TemplateMaskUpdatePayload,
  TemplateUpdatePayload,
  BaselineRevisionCreatePayload
} from '@/types/models'

export interface ListTemplatesParams {
  keyword?: string
  status?: string
  templateType?: string
}

function mapMaskRegion(item: MaskRegionReadDTO): MaskRegion {
  return {
    id: item.id,
    name: item.region_name,
    xRatio: Number(item.x_ratio),
    yRatio: Number(item.y_ratio),
    widthRatio: Number(item.width_ratio),
    heightRatio: Number(item.height_ratio),
    sortOrder: item.sort_order
  }
}

function mapMaskRegions(items: MaskRegionReadDTO[]) {
  return items.map(mapMaskRegion)
}

function mapBaselineRevision(item: BaselineRevisionReadDTO): BaselineRevision {
  return {
    id: item.id,
    templateId: item.template_id,
    revisionNo: item.revision_no,
    mediaObjectId: item.media_object_id,
    sourceType: item.source_type,
    isCurrent: item.is_current,
    remark: item.remark ?? '',
    createdAt: item.created_at
  }
}

function mapBaselineRevisions(items: BaselineRevisionReadDTO[]) {
  return items.map(mapBaselineRevision)
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
    baselineRevisions: [],
    maskRegions: []
  }
}

export async function listTemplates(params: ListTemplatesParams = {}): Promise<Template[]> {
  const keyword = params.keyword?.trim()
  const response = await requestPage<TemplateReadDTO>({
    method: 'get',
    url: '/templates',
    params: {
      page: 1,
      page_size: 100,
      keyword: keyword || undefined,
      status: params.status || undefined,
      template_type: params.templateType || undefined
    }
  })

  return response.data.map(mapTemplateSummary)
}

export async function createTemplate(payload: TemplateCreatePayload): Promise<Template> {
  const response = await requestData<TemplateReadDTO>({
    method: 'post',
    url: '/templates',
    data: {
      template_code: payload.code,
      template_name: payload.name,
      template_type: payload.templateType,
      match_strategy: payload.matchStrategy,
      threshold_value: payload.thresholdValue,
      status: payload.status,
      original_media_object_id: payload.originalMediaObjectId
    }
  })

  return mapTemplateSummary(response)
}

export async function updateTemplate(
  templateId: number,
  payload: TemplateUpdatePayload
): Promise<Template> {
  const response = await requestData<TemplateReadDTO>({
    method: 'patch',
    url: `/templates/${templateId}`,
    data: {
      template_name: payload.name,
      template_type: payload.templateType,
      match_strategy: payload.matchStrategy,
      threshold_value: payload.thresholdValue,
      status: payload.status
    }
  })

  return mapTemplateSummary(response)
}

export async function listBaselineRevisions(templateId: number): Promise<BaselineRevision[]> {
  const response = await requestData<BaselineRevisionReadDTO[]>({
    method: 'get',
    url: `/templates/${templateId}/baseline-revisions`
  })

  return mapBaselineRevisions(response)
}

export async function createBaselineRevision(
  templateId: number,
  payload: BaselineRevisionCreatePayload
): Promise<BaselineRevision> {
  const response = await requestData<BaselineRevisionReadDTO>({
    method: 'post',
    url: `/templates/${templateId}/baseline-revisions`,
    data: {
      media_object_id: payload.mediaObjectId,
      source_type: payload.sourceType,
      remark: payload.remark,
      is_current: payload.isCurrent
    }
  })

  return mapBaselineRevision(response)
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
    baselineRevisions: mapBaselineRevisions(baselineRevisions),
    maskRegions: mapMaskRegions(maskRegions)
  }
}

export async function createMaskRegion(
  templateId: number,
  payload: TemplateMaskCreatePayload
): Promise<MaskRegion> {
  const response = await requestData<MaskRegionReadDTO>({
    method: 'post',
    url: `/templates/${templateId}/mask-regions`,
    data: {
      name: payload.name,
      x_ratio: payload.xRatio,
      y_ratio: payload.yRatio,
      width_ratio: payload.widthRatio,
      height_ratio: payload.heightRatio,
      sort_order: payload.sortOrder
    }
  })

  return mapMaskRegion(response)
}

export async function updateMaskRegion(
  _templateId: number,
  maskRegionId: number,
  payload: TemplateMaskUpdatePayload
): Promise<MaskRegion> {
  const response = await requestData<MaskRegionReadDTO>({
    method: 'patch',
    url: `/mask-regions/${maskRegionId}`,
    data: {
      name: payload.name,
      x_ratio: payload.xRatio,
      y_ratio: payload.yRatio,
      width_ratio: payload.widthRatio,
      height_ratio: payload.heightRatio,
      sort_order: payload.sortOrder
    }
  })

  return mapMaskRegion(response)
}

export async function deleteMaskRegion(_templateId: number, maskRegionId: number): Promise<void> {
  await requestVoid({
    method: 'delete',
    url: `/mask-regions/${maskRegionId}`
  })
}
