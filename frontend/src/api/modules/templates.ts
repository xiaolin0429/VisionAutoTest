import { requestData, requestPage } from '@/api/client'
import { TEMPLATE_MASK_STORAGE_KEY } from '@/constants/storage'
import type {
  BaselineRevisionReadDTO,
  MaskRegionReadDTO,
  TemplateReadDTO
} from '@/types/backend'
import type {
  MaskRegion,
  Template,
  TemplateMaskCreatePayload,
  TemplateMaskUpdatePayload
} from '@/types/models'

type TemplateMaskStore = Record<string, MaskRegion[]>

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

function cloneMaskRegion(item: MaskRegion): MaskRegion {
  return {
    id: item.id,
    name: item.name,
    xRatio: item.xRatio,
    yRatio: item.yRatio,
    widthRatio: item.widthRatio,
    heightRatio: item.heightRatio,
    sortOrder: item.sortOrder
  }
}

function normalizeMaskRegions(items: MaskRegion[]) {
  return [...items]
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .map((item, index) => ({
      ...cloneMaskRegion(item),
      sortOrder: index + 1
    }))
}

function readMaskStore() {
  const raw = localStorage.getItem(TEMPLATE_MASK_STORAGE_KEY)
  if (!raw) {
    return {} as TemplateMaskStore
  }

  try {
    return JSON.parse(raw) as TemplateMaskStore
  } catch {
    localStorage.removeItem(TEMPLATE_MASK_STORAGE_KEY)
    return {} as TemplateMaskStore
  }
}

function writeMaskStore(store: TemplateMaskStore) {
  localStorage.setItem(TEMPLATE_MASK_STORAGE_KEY, JSON.stringify(store))
}

function getStoredMaskRegions(templateId: number) {
  const store = readMaskStore()
  const key = String(templateId)
  return store[key]?.map(cloneMaskRegion) ?? null
}

function persistTemplateMaskRegions(templateId: number, items: MaskRegion[]) {
  const store = readMaskStore()
  store[String(templateId)] = normalizeMaskRegions(items)
  writeMaskStore(store)
  return store[String(templateId)].map(cloneMaskRegion)
}

function ensureStoredMaskRegions(templateId: number, fallback: MaskRegion[]) {
  const stored = getStoredMaskRegions(templateId)
  if (stored) {
    return stored
  }

  return persistTemplateMaskRegions(templateId, fallback)
}

function getNextMaskRegionId(items: MaskRegion[]) {
  return items.reduce((maxValue, item) => Math.max(maxValue, item.id), 0) + 1
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
    maskRegions: ensureStoredMaskRegions(templateId, mapMaskRegions(maskRegions))
  }
}

export async function createMaskRegion(
  templateId: number,
  payload: TemplateMaskCreatePayload
): Promise<MaskRegion> {
  const currentRegions = getStoredMaskRegions(templateId) ?? []
  const nextRegion: MaskRegion = {
    id: getNextMaskRegionId(currentRegions),
    name: payload.name,
    xRatio: payload.xRatio,
    yRatio: payload.yRatio,
    widthRatio: payload.widthRatio,
    heightRatio: payload.heightRatio,
    sortOrder: payload.sortOrder
  }

  persistTemplateMaskRegions(templateId, [...currentRegions, nextRegion])
  return cloneMaskRegion(nextRegion)
}

export async function updateMaskRegion(
  templateId: number,
  maskRegionId: number,
  payload: TemplateMaskUpdatePayload
): Promise<MaskRegion> {
  const currentRegions = getStoredMaskRegions(templateId) ?? []
  const nextRegions = currentRegions.map((item) => {
    if (item.id !== maskRegionId) {
      return item
    }

    return {
      ...item,
      ...payload
    }
  })

  const stored = persistTemplateMaskRegions(templateId, nextRegions)
  const updated = stored.find((item) => item.id === maskRegionId)
  if (!updated) {
    throw new Error(`Mask region ${maskRegionId} not found.`)
  }

  return cloneMaskRegion(updated)
}

export async function deleteMaskRegion(templateId: number, maskRegionId: number): Promise<void> {
  const currentRegions = getStoredMaskRegions(templateId) ?? []
  const nextRegions = currentRegions.filter((item) => item.id !== maskRegionId)
  persistTemplateMaskRegions(templateId, nextRegions)
}
