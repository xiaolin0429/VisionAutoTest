<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { formatRatio } from '@/utils/format'
import type { MaskRegion, TemplateCanvasInteractionHandle } from '@/types/models'

const props = withDefaults(
  defineProps<{
    templateType: string
    imageLabel?: string
    regions: MaskRegion[]
    editable?: boolean
    selectedMaskId?: number | null
  }>(),
  {
    imageLabel: '模板预览',
    editable: false,
    selectedMaskId: null
  }
)

const emit = defineEmits<{
  (event: 'update:regions', value: MaskRegion[]): void
  (event: 'update:selectedMaskId', value: number | null): void
}>()

type ResizeHandle = Exclude<TemplateCanvasInteractionHandle, 'move'>

interface PointRatio {
  x: number
  y: number
}

interface InteractionState {
  type: 'create' | 'move' | 'resize'
  regionId: number
  startPoint: PointRatio
  baseRegion: MaskRegion
  handle?: ResizeHandle
}

const MIN_REGION_RATIO = 0.04

const boardRef = ref<HTMLDivElement | null>(null)
const activeInteraction = ref<InteractionState | null>(null)

const boardStyle = computed(() => {
  return props.templateType === 'mobile_screen'
    ? { aspectRatio: '9 / 19.5' }
    : { aspectRatio: '16 / 10' }
})

function roundRatio(value: number) {
  return Number(value.toFixed(4))
}

function clamp(value: number, minValue: number, maxValue: number) {
  return Math.min(Math.max(value, minValue), maxValue)
}

function createRegionStyle(region: MaskRegion) {
  return {
    left: `${region.xRatio * 100}%`,
    top: `${region.yRatio * 100}%`,
    width: `${region.widthRatio * 100}%`,
    height: `${region.heightRatio * 100}%`
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
  const board = boardRef.value
  if (!board) {
    return null
  }

  const bounds = board.getBoundingClientRect()
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

function startCreate(event: MouseEvent) {
  if (!props.editable) {
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

  if (!props.editable) {
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

  if (!props.editable) {
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

function handleBoardMouseDown(event: MouseEvent) {
  if (!props.editable) {
    return
  }

  startCreate(event)
}

function handleWindowMouseMove(event: MouseEvent) {
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
  removeWindowListeners()
}

onBeforeUnmount(() => {
  removeWindowListeners()
})
</script>

<template>
  <div class="space-y-4">
    <div class="relative overflow-hidden rounded-3xl border border-slate-200 bg-slate-900 p-4">
      <div
        ref="boardRef"
        :style="boardStyle"
        :class="[
          'relative overflow-hidden rounded-2xl border border-white/10',
          editable ? 'cursor-crosshair' : 'cursor-default'
        ]"
        @mousedown="handleBoardMouseDown"
      >
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.6),_rgba(15,23,42,1)_55%)]" />
        <div class="absolute inset-0 bg-[linear-gradient(0deg,_rgba(255,255,255,0.06)_1px,_transparent_1px),linear-gradient(90deg,_rgba(255,255,255,0.06)_1px,_transparent_1px)] bg-[size:36px_36px]" />
        <div class="absolute inset-0 bg-[linear-gradient(135deg,_rgba(255,255,255,0.12),_transparent_35%,_rgba(59,130,246,0.18))]" />
        <div class="absolute left-6 top-6 rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
          {{ imageLabel }}
        </div>
        <div class="absolute bottom-4 left-4 rounded-xl bg-slate-950/70 px-3 py-2 text-xs text-slate-200">
          {{ editable ? '拖拽空白区域可创建 Mask，拖拽边框可调整位置与尺寸' : '占位预览底图' }}
        </div>

        <button
          v-for="region in regions"
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

        <div
          v-if="regions.length === 0"
          class="absolute inset-0 flex items-center justify-center text-sm text-slate-300"
        >
          当前模板暂无忽略区域
        </div>
      </div>
    </div>
  </div>
</template>
