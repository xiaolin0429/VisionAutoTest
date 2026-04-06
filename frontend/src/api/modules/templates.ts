import { requestData, requestPage, requestVoid } from '@/api/client'
import type {
  BaselineRevisionReadDTO,
  TemplateOCRResultReadDTO,
  TemplatePreviewReadDTO,
  MaskRegionReadDTO,
  TemplateReadDTO
} from '@/types/backend'
import type {
  BaselineRevision,
  MaskRegion,
  Template,
  TemplateOcrResult,
  TemplateOcrBlock,
  TemplatePreviewState,
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
  // @param item Backend mask-region DTO.
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
  // @param item Backend baseline-revision DTO.
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

function mapPreviewMaskRegion(item: {
  name: string
  x_ratio: number
  y_ratio: number
  width_ratio: number
  height_ratio: number
  sort_order: number
}): MaskRegion {
  return {
    id: -(item.sort_order || 1),
    name: item.name,
    xRatio: Number(item.x_ratio),
    yRatio: Number(item.y_ratio),
    widthRatio: Number(item.width_ratio),
    heightRatio: Number(item.height_ratio),
    sortOrder: item.sort_order
  }
}

function mapTemplateOcrBlock(
  resultId: number | null,
  item: TemplateOCRResultReadDTO['blocks'][number]
): TemplateOcrBlock {
  // @param resultId OCR result id used to create stable block ids for frontend selection state.
  // @param item Backend OCR block DTO.
  return {
    id: `${resultId ?? 'pending'}-${item.order_no}`,
    text: item.text,
    confidence: Number(item.confidence),
    orderNo: item.order_no,
    polygonPoints: item.polygon_points.map((point) => ({
      x: point.x,
      y: point.y
    })),
    pixelRect: {
      x: item.pixel_rect.x,
      y: item.pixel_rect.y,
      width: item.pixel_rect.width,
      height: item.pixel_rect.height
    },
    ratioRect: {
      xRatio: Number(item.ratio_rect.x_ratio),
      yRatio: Number(item.ratio_rect.y_ratio),
      widthRatio: Number(item.ratio_rect.width_ratio),
      heightRatio: Number(item.ratio_rect.height_ratio)
    },
    highlighted: false
  }
}

function mapTemplateOcrResult(item: TemplateOCRResultReadDTO): TemplateOcrResult {
  // @param item Backend template OCR result DTO.
  return {
    id: item.id,
    templateId: item.template_id,
    baselineRevisionId: item.baseline_revision_id,
    sourceMediaObjectId: item.source_media_object_id,
    status: item.status,
    engineName: item.engine_name,
    imageWidth: item.image_width,
    imageHeight: item.image_height,
    errorCode: item.error_code,
    errorMessage: item.error_message,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    blocks: item.blocks.map((block) => mapTemplateOcrBlock(item.id, block))
  }
}

function mapTemplatePreviewState(
  item: TemplatePreviewReadDTO,
  message = '预览生成成功。'
): TemplatePreviewState {
  // @param item Backend processed-preview DTO.
  // @param message UI message attached to the mapped preview state.
  return {
    status: 'ready',
    baselineRevisionId: item.baseline_revision_id,
    sourceMediaObjectId: item.source_media_object_id,
    overlayMediaObjectId: item.overlay_media_object_id,
    overlayImageUrl: item.overlay_content_url,
    processedMediaObjectId: item.processed_media_object_id,
    processedImageUrl: item.processed_content_url,
    imageWidth: item.image_width,
    imageHeight: item.image_height,
    maskRegions: item.mask_regions.map(mapPreviewMaskRegion),
    message
  }
}

function resolveBaselineVersion(
  currentBaselineRevisionId: number | null,
  revisions: BaselineRevisionReadDTO[]
) {
  // @param currentBaselineRevisionId Current baseline revision id stored on the template summary.
  // @param revisions Full revision list used to turn the id into a human-readable version label.
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
  // @param item Backend template summary DTO.
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
  // @param params Optional keyword/status/type filters for the template list page.
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
  // @param payload Frontend create payload for template creation.
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
  // @param templateId Template id being updated.
  // @param payload Frontend update payload for the template summary fields.
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
  // @param templateId Template id whose baseline revision list should be loaded.
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
  // @param templateId Parent template id.
  // @param payload Frontend baseline-revision create payload.
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
  // @param templateId Template id whose summary, baseline list, and mask regions should be aggregated.
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
  // @param templateId Parent template id.
  // @param payload Frontend mask-region create payload.
  const response = await requestData<MaskRegionReadDTO>({
    method: 'post',
    url: `/templates/${templateId}/mask-regions`,
    data: {
      region_name: payload.name,
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
  // @param _templateId Unused compatibility parameter kept to match caller context.
  // @param maskRegionId Target mask-region id.
  // @param payload Frontend mask-region update payload.
  const response = await requestData<MaskRegionReadDTO>({
    method: 'patch',
    url: `/mask-regions/${maskRegionId}`,
    data: {
      region_name: payload.name,
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
  // @param _templateId Unused compatibility parameter kept to match caller context.
  // @param maskRegionId Target mask-region id to delete.
  await requestVoid({
    method: 'delete',
    url: `/mask-regions/${maskRegionId}`
  })
}

export async function requestTemplateOcrAnalysis(
  templateId: number,
  baselineRevisionId: number
): Promise<TemplateOcrResult> {
  // @param templateId Parent template id.
  // @param baselineRevisionId Baseline revision whose OCR analysis should be triggered.
  const response = await requestData<TemplateOCRResultReadDTO>({
    method: 'post',
    url: `/templates/${templateId}/baseline-revisions/${baselineRevisionId}/ocr-results`
  })

  return mapTemplateOcrResult(response)
}

export async function listTemplateOcrResults(
  templateId: number,
  baselineRevisionId: number
): Promise<TemplateOcrResult> {
  // @param templateId Parent template id.
  // @param baselineRevisionId Baseline revision whose latest OCR result should be loaded.
  const response = await requestData<TemplateOCRResultReadDTO>({
    method: 'get',
    url: `/templates/${templateId}/baseline-revisions/${baselineRevisionId}/ocr-results`
  })

  return mapTemplateOcrResult(response)
}

export async function getTemplateProcessedPreview(
  templateId: number,
  baselineRevisionId: number,
  maskRegions?: TemplateMaskCreatePayload[]
): Promise<TemplatePreviewState> {
  // @param templateId Parent template id.
  // @param baselineRevisionId Baseline revision whose preview should be generated.
  // @param maskRegions Optional draft mask list used to preview unsaved edits.
  const response = await requestData<TemplatePreviewReadDTO>({
    method: 'post',
    url: `/templates/${templateId}/baseline-revisions/${baselineRevisionId}/preview-images`,
    data: maskRegions
      ? {
          mask_regions: maskRegions.map((item) => ({
            name: item.name,
            x_ratio: item.xRatio,
            y_ratio: item.yRatio,
            width_ratio: item.widthRatio,
            height_ratio: item.heightRatio,
            sort_order: item.sortOrder
          }))
        }
      : {}
  })

  return mapTemplatePreviewState(response)
}
