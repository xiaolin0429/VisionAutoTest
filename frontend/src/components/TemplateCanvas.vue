<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { formatRatio } from '@/utils/format'
import type {
  MaskRegion,
  TemplateCanvasInteractionHandle,
  TemplateOcrBlock,
  TemplateWorkbenchViewMode
} from '@/types/models'

const props = withDefaults(
  defineProps<{
    templateType: string
    imageLabel?: string
    regions: MaskRegion[]
    ocrBlocks?: TemplateOcrBlock[]
    editable?: boolean
    selectedMaskId?: number | null
    selectedOcrResultId?: string | null
    viewMode?: TemplateWorkbenchViewMode
    imageUrl?: string | null
    overlayImageUrl?: string | null
    processedImageUrl?: string | null
    imageLoading?: boolean
    imageError?: string
    previewState?: { message: string } | null
  }>(),
  {
    imageLabel: '模板预览',
    ocrBlocks: () => [],
    editable: false,
    selectedMaskId: null,
    selectedOcrResultId: null,
    viewMode: 'mask',
    imageUrl: null,
    overlayImageUrl: null,
    processedImageUrl: null,
    imageLoading: false,
    imageError: '',
    previewState: null
  }
)

const emit = defineEmits<{
  (event: 'update:regions', value: MaskRegion[]): void
  (event: 'update:selectedMaskId', value: number | null): void
  (event: 'update:selectedOcrResultId', value: string | null): void
}>()

type ResizeHandle = Exclude<TemplateCanvasInteractionHandle, 'move'>

interface PointRatio {
  x: number
  y: number
}

interface RegionInteractionState {
  type: 'create' | 'move' | 'resize'
  regionId: number
  startPoint: PointRatio
  baseRegion: MaskRegion
  handle?: ResizeHandle
}

interface PanInteractionState {
  startClientX: number
  startClientY: number
  originTranslateX: number
  originTranslateY: number
}

const MIN_REGION_RATIO = 0.04
const MIN_SCALE = 1
const MAX_SCALE = 4

const boardRef = ref<HTMLDivElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
const activeInteraction = ref<RegionInteractionState | null>(null)
const activePan = ref<PanInteractionState | null>(null)
const imageAspectRatio = ref<number | null>(null)
const isSpacePressed = ref(false)

const viewport = reactive({
  scale: 1,
  translateX: 0,
  translateY: 0
})

const activeImageUrl = computed(() => {
  if (props.viewMode === 'processed') {
    return props.processedImageUrl ?? props.imageUrl ?? null
  }

  if (props.viewMode === 'mask' && !props.editable) {
    return props.overlayImageUrl ?? props.imageUrl ?? null
  }

  return props.imageUrl ?? null
})

const canEditMask = computed(() => {
  return props.viewMode === 'mask' && props.editable && Boolean(props.imageUrl)
})

const resolvedOcrResults = computed(() => {
  return props.ocrBlocks.map((item) => ({
    ...item,
    highlighted: item.highlighted || props.selectedOcrResultId === item.id
  }))
})

const boardStyle = computed(() => {
  if (imageAspectRatio.value && Number.isFinite(imageAspectRatio.value)) {
    return { aspectRatio: String(imageAspectRatio.value) }
  }

  return props.templateType === 'mobile_screen'
    ? { aspectRatio: '9 / 19.5' }
    : { aspectRatio: '16 / 10' }
})

const stageStyle = computed(() => {
  return {
    transform: `translate(${viewport.translateX}px, ${viewport.translateY}px) scale(${viewport.scale})`,
    transformOrigin: 'center center'
  }
})

const zoomLabel = computed(() => `${Math.round(viewport.scale * 100)}%`)

const previewMessage = computed(() => {
  if (props.imageLoading) {
    return '正在加载当前基准图...'
  }

  if (props.imageError) {
    return props.imageError
  }

  if (!props.imageUrl) {
    return '当前模板暂无可用基准图。'
  }

  if (props.viewMode === 'mask' && !props.editable && !props.overlayImageUrl) {
    return props.previewState?.message || 'Mask 叠加预览尚未生成。'
  }

  if (props.viewMode === 'ocr' && resolvedOcrResults.value.length === 0) {
    return props.previewState?.message || '当前基准版本暂无 OCR 结果。'
  }

  if (props.viewMode === 'processed' && !props.processedImageUrl) {
    return props.previewState?.message || '当前处理后预览尚未生成。'
  }

  return ''
})

const helperText = computed(() => {
  if (props.viewMode === 'mask') {
    return canEditMask.value
      ? '滚轮缩放，按住空格拖拽平移，拖拽空白区域创建 Mask。'
      : '当前为 Mask 视图，可查看区域覆盖效果。'
  }

  if (props.viewMode === 'ocr') {
    return 'OCR 视图将叠加识别框，并支持结果列表联动高亮。'
  }

  if (props.viewMode === 'processed') {
    return '处理后视图用于展示 Mask 生效后的图片结果。'
  }

  return '原图视图用于核对当前工作基准图。'
})

function roundRatio(value: number) {
  return Number(value.toFixed(4))
}

function clamp(value: number, minValue: number, maxValue: number) {
  return Math.min(Math.max(value, minValue), maxValue)
}

function resetViewport() {
  viewport.scale = 1
  viewport.translateX = 0
  viewport.translateY = 0
}

function setScale(nextScale: number) {
  const normalizedScale = clamp(Number(nextScale.toFixed(2)), MIN_SCALE, MAX_SCALE)
  viewport.scale = normalizedScale

  if (normalizedScale === MIN_SCALE) {
    viewport.translateX = 0
    viewport.translateY = 0
  }
}

function zoomIn() {
  setScale(viewport.scale + 0.2)
}

function zoomOut() {
  setScale(viewport.scale - 0.2)
}

function createRegionStyle(region: MaskRegion) {
  return {
    left: `${region.xRatio * 100}%`,
    top: `${region.yRatio * 100}%`,
    width: `${region.widthRatio * 100}%`,
    height: `${region.heightRatio * 100}%`
  }
}

function createOcrStyle(result: TemplateOcrBlock) {
  return {
    left: `${result.ratioRect.xRatio * 100}%`,
    top: `${result.ratioRect.yRatio * 100}%`,
    width: `${result.ratioRect.widthRatio * 100}%`,
    height: `${result.ratioRect.heightRatio * 100}%`
  }
}

function createHandleStyle(handle: ResizeHandle) {
  const positionMap: Record<ResizeHandle, Record<string, string>> = {
    nw: { left: '-6px', top: '-6px', cursor: 'nwse-resize' },
    ne: { right: '-6px', top: '-6px', cursor: 'nesw-resize' },
    sw: { left: '-6px', bottom: '-6px', cursor: 'nesw-resize' },
    se: { right: '-6px', bottom: '-6px', cursor: 'nwse-resize' }
  }

  return positionMap[handle]
}

function cloneRegion(region: MaskRegion): MaskRegion {
  return {
    id: region.id,
    name: region.name,
    xRatio: region.xRatio,
    yRatio: region.yRatio,
    widthRatio: region.widthRatio,
    heightRatio: region.heightRatio,
    sortOrder: region.sortOrder
  }
}

function normalizeRegions(items: MaskRegion[]) {
  return [...items]
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .map((item, index) => ({
      ...cloneRegion(item),
      sortOrder: index + 1
    }))
}

function getRegionNextDraftId() {
  const minimumId = props.regions.reduce((currentMin, item) => Math.min(currentMin, item.id), 0)
  return minimumId - 1
}

function getBoardPoint(event: MouseEvent) {
  const stage = stageRef.value ?? boardRef.value
  if (!stage) {
    return null
  }

  const bounds = stage.getBoundingClientRect()
  const x = clamp((event.clientX - bounds.left) / bounds.width, 0, 1)
  const y = clamp((event.clientY - bounds.top) / bounds.height, 0, 1)

  return {
    x: roundRatio(x),
    y: roundRatio(y)
  }
}

function clampRegion(region: MaskRegion): MaskRegion {
  const widthRatio = clamp(region.widthRatio, MIN_REGION_RATIO, 1)
  const heightRatio = clamp(region.heightRatio, MIN_REGION_RATIO, 1)
  const xRatio = clamp(region.xRatio, 0, 1 - widthRatio)
  const yRatio = clamp(region.yRatio, 0, 1 - heightRatio)

  return {
    ...region,
    xRatio: roundRatio(xRatio),
    yRatio: roundRatio(yRatio),
    widthRatio: roundRatio(widthRatio),
    heightRatio: roundRatio(heightRatio)
  }
}

function createRegionFromBounds(
  id: number,
  name: string,
  sortOrder: number,
  startPoint: PointRatio,
  endPoint: PointRatio
) {
  const xRatio = Math.min(startPoint.x, endPoint.x)
  const yRatio = Math.min(startPoint.y, endPoint.y)
  const widthRatio = Math.max(Math.abs(endPoint.x - startPoint.x), MIN_REGION_RATIO)
  const heightRatio = Math.max(Math.abs(endPoint.y - startPoint.y), MIN_REGION_RATIO)

  return clampRegion({
    id,
    name,
    sortOrder,
    xRatio,
    yRatio,
    widthRatio,
    heightRatio
  })
}

function replaceRegion(nextRegion: MaskRegion) {
  const baseRegions = props.regions.some((item) => item.id === nextRegion.id)
    ? props.regions
    : [...props.regions, nextRegion]
  const nextRegions = baseRegions.map((item) => {
    return item.id === nextRegion.id ? nextRegion : item
  })
  emit('update:regions', normalizeRegions(nextRegions))
}

function removeWindowListeners() {
  window.removeEventListener('mousemove', handleWindowMouseMove)
  window.removeEventListener('mouseup', handleWindowMouseUp)
}

function bindWindowListeners() {
  removeWindowListeners()
  window.addEventListener('mousemove', handleWindowMouseMove)
  window.addEventListener('mouseup', handleWindowMouseUp)
}

function selectRegion(maskRegionId: number | null) {
  emit('update:selectedMaskId', maskRegionId)
}

function selectOcrResult(resultId: string | null) {
  emit('update:selectedOcrResultId', resultId)
}

function startPan(event: MouseEvent) {
  if (!activeImageUrl.value) {
    return
  }

  event.preventDefault()
  activePan.value = {
    startClientX: event.clientX,
    startClientY: event.clientY,
    originTranslateX: viewport.translateX,
    originTranslateY: viewport.translateY
  }
  bindWindowListeners()
}

function startCreate(event: MouseEvent) {
  if (!canEditMask.value) {
    return
  }

  const point = getBoardPoint(event)
  if (!point) {
    return
  }

  const regionId = getRegionNextDraftId()
  const nextRegion = createRegionFromBounds(
    regionId,
    `未命名区域 ${props.regions.length + 1}`,
    props.regions.length + 1,
    point,
    point
  )

  emit('update:regions', normalizeRegions([...props.regions, nextRegion]))
  selectRegion(regionId)
  activeInteraction.value = {
    type: 'create',
    regionId,
    startPoint: point,
    baseRegion: nextRegion
  }
  bindWindowListeners()
}

function startMove(region: MaskRegion, event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  selectRegion(region.id)

  if (!canEditMask.value) {
    return
  }

  const point = getBoardPoint(event)
  if (!point) {
    return
  }

  activeInteraction.value = {
    type: 'move',
    regionId: region.id,
    startPoint: point,
    baseRegion: cloneRegion(region)
  }
  bindWindowListeners()
}

function startResize(region: MaskRegion, handle: ResizeHandle, event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  selectRegion(region.id)

  if (!canEditMask.value) {
    return
  }

  const point = getBoardPoint(event)
  if (!point) {
    return
  }

  activeInteraction.value = {
    type: 'resize',
    regionId: region.id,
    startPoint: point,
    baseRegion: cloneRegion(region),
    handle
  }
  bindWindowListeners()
}

function shouldStartPan(event: MouseEvent) {
  if (!activeImageUrl.value) {
    return false
  }

  if (event.button === 1 || event.button === 2 || isSpacePressed.value) {
    return true
  }

  return props.viewMode !== 'mask' || !props.editable
}

function handleBoardMouseDown(event: MouseEvent) {
  if (props.imageLoading || previewMessage.value === props.imageError) {
    return
  }

  if (shouldStartPan(event)) {
    startPan(event)
    return
  }

  if (event.button !== 0) {
    return
  }

  startCreate(event)
}

function handleBoardWheel(event: WheelEvent) {
  if (!activeImageUrl.value) {
    return
  }

  event.preventDefault()
  setScale(viewport.scale + (event.deltaY < 0 ? 0.2 : -0.2))
}

function handleWindowMouseMove(event: MouseEvent) {
  if (activePan.value) {
    viewport.translateX =
      activePan.value.originTranslateX + (event.clientX - activePan.value.startClientX)
    viewport.translateY =
      activePan.value.originTranslateY + (event.clientY - activePan.value.startClientY)
    return
  }

  const interaction = activeInteraction.value
  if (!interaction) {
    return
  }

  const point = getBoardPoint(event)
  if (!point) {
    return
  }

  if (interaction.type === 'create') {
    const nextRegion = createRegionFromBounds(
      interaction.regionId,
      interaction.baseRegion.name,
      interaction.baseRegion.sortOrder,
      interaction.startPoint,
      point
    )
    replaceRegion(nextRegion)
    return
  }

  if (interaction.type === 'move') {
    const deltaX = point.x - interaction.startPoint.x
    const deltaY = point.y - interaction.startPoint.y
    const nextRegion = clampRegion({
      ...interaction.baseRegion,
      xRatio: interaction.baseRegion.xRatio + deltaX,
      yRatio: interaction.baseRegion.yRatio + deltaY
    })
    replaceRegion(nextRegion)
    return
  }

  if (interaction.type === 'resize' && interaction.handle) {
    const baseRegion = interaction.baseRegion
    const corners: Record<ResizeHandle, PointRatio> = {
      nw: {
        x: baseRegion.xRatio + baseRegion.widthRatio,
        y: baseRegion.yRatio + baseRegion.heightRatio
      },
      ne: {
        x: baseRegion.xRatio,
        y: baseRegion.yRatio + baseRegion.heightRatio
      },
      sw: {
        x: baseRegion.xRatio + baseRegion.widthRatio,
        y: baseRegion.yRatio
      },
      se: {
        x: baseRegion.xRatio,
        y: baseRegion.yRatio
      }
    }
    const anchor = corners[interaction.handle]
    const nextRegion = createRegionFromBounds(
      interaction.regionId,
      baseRegion.name,
      baseRegion.sortOrder,
      anchor,
      point
    )
    replaceRegion(nextRegion)
  }
}

function handleWindowMouseUp() {
  activeInteraction.value = null
  activePan.value = null
  removeWindowListeners()
}

function handleImageLoad(event: Event) {
  const image = event.target as HTMLImageElement
  if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
    return
  }

  imageAspectRatio.value = Number((image.naturalWidth / image.naturalHeight).toFixed(4))
}

function handleWindowKeyDown(event: KeyboardEvent) {
  if (event.code === 'Space') {
    isSpacePressed.value = true
  }
}

function handleWindowKeyUp(event: KeyboardEvent) {
  if (event.code === 'Space') {
    isSpacePressed.value = false
  }
}

function handleWindowBlur() {
  isSpacePressed.value = false
}

watch(
  () => [props.imageUrl, props.processedImageUrl, props.viewMode],
  () => {
    imageAspectRatio.value = null
    resetViewport()
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleWindowKeyDown)
  window.addEventListener('keyup', handleWindowKeyUp)
  window.addEventListener('blur', handleWindowBlur)
})

onBeforeUnmount(() => {
  removeWindowListeners()
  window.removeEventListener('keydown', handleWindowKeyDown)
  window.removeEventListener('keyup', handleWindowKeyUp)
  window.removeEventListener('blur', handleWindowBlur)
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500">
        {{ helperText }}
      </div>

      <div class="flex items-center gap-2">
        <span class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500">
          {{ zoomLabel }}
        </span>
        <el-button-group>
          <el-button plain @click="zoomOut">
            缩小
          </el-button>
          <el-button plain @click="resetViewport">
            重置视图
          </el-button>
          <el-button plain @click="zoomIn">
            放大
          </el-button>
        </el-button-group>
      </div>
    </div>

    <div
      v-loading="imageLoading"
      class="relative overflow-hidden rounded-3xl border border-slate-200 bg-slate-900 p-4"
    >
      <div
        ref="boardRef"
        :style="boardStyle"
        :class="[
          'relative overflow-hidden rounded-2xl border border-white/10 bg-slate-950',
          canEditMask ? 'cursor-crosshair' : 'cursor-grab'
        ]"
        @contextmenu.prevent
        @mousedown="handleBoardMouseDown"
        @wheel="handleBoardWheel"
      >
        <div
          ref="stageRef"
          :style="stageStyle"
          class="absolute inset-0"
        >
          <img
            v-if="activeImageUrl"
            :src="activeImageUrl"
            class="h-full w-full select-none object-fill"
            draggable="false"
            @load="handleImageLoad"
          >
          <div
            v-else
            class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.45),_rgba(15,23,42,1)_58%)]"
          />

          <button
            v-for="result in resolvedOcrResults"
            v-show="viewMode === 'ocr'"
            :key="result.id"
            :style="createOcrStyle(result)"
            :class="[
              'absolute rounded-xl border-2 transition',
              result.highlighted
                ? 'border-emerald-300 bg-emerald-300/15 shadow-lg shadow-emerald-950/20'
                : 'border-sky-300 bg-sky-300/10'
            ]"
            type="button"
            @click.stop="selectOcrResult(result.id)"
          >
            <span
              :class="[
                'absolute -top-7 left-0 rounded-lg px-2 py-1 text-xs font-medium',
                result.highlighted
                  ? 'bg-emerald-300 text-slate-900'
                  : 'bg-sky-300 text-slate-900'
              ]"
            >
              {{ result.orderNo }} · {{ result.text || '未识别文本' }}
            </span>
          </button>

          <button
            v-for="region in regions"
            v-show="viewMode === 'mask'"
            :key="region.id"
            :style="createRegionStyle(region)"
            :class="[
              'absolute rounded-xl border-2 text-left transition',
              selectedMaskId === region.id
                ? 'border-brand-400 bg-brand-400/20 shadow-lg shadow-brand-950/20'
                : 'border-amber-300 bg-amber-300/20 shadow-lg shadow-amber-950/10'
            ]"
            type="button"
            @mousedown="startMove(region, $event)"
          >
            <span
              :class="[
                'absolute -top-7 left-0 rounded-lg px-2 py-1 text-xs font-medium',
                selectedMaskId === region.id
                  ? 'bg-brand-400 text-white'
                  : 'bg-amber-300 text-slate-900'
              ]"
            >
              {{ region.name }}
            </span>

            <span
              v-if="selectedMaskId === region.id"
              class="absolute inset-x-0 bottom-0 rounded-b-xl bg-slate-950/70 px-2 py-1 text-[11px] text-white"
            >
              {{ formatRatio(region.xRatio) }} / {{ formatRatio(region.yRatio) }}
            </span>

            <span
              v-for="handle in ['nw', 'ne', 'sw', 'se']"
              v-if="editable && selectedMaskId === region.id"
              :key="handle"
              :style="createHandleStyle(handle as ResizeHandle)"
              class="absolute h-3 w-3 rounded-full border-2 border-white bg-brand-500"
              @mousedown="startResize(region, handle as ResizeHandle, $event)"
            />
          </button>
        </div>

        <div class="pointer-events-none absolute left-6 top-6 rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
          {{ imageLabel }}
        </div>
        <div class="pointer-events-none absolute bottom-4 left-4 rounded-xl bg-slate-950/70 px-3 py-2 text-xs text-slate-200">
          {{ helperText }}
        </div>

        <div
          v-if="previewMessage"
          class="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/45 p-6"
        >
          <div class="max-w-md rounded-2xl border border-white/10 bg-slate-950/85 px-5 py-4 text-center text-sm leading-6 text-slate-200">
            {{ previewMessage }}
          </div>
        </div>

        <div
          v-else-if="viewMode === 'mask' && regions.length === 0"
          class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-slate-300"
        >
          当前模板暂无忽略区域
        </div>
      </div>
    </div>
  </div>
</template>
