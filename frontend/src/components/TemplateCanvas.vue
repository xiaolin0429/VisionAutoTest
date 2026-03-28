<script setup lang="ts">
import { computed } from 'vue'
import { formatRatio } from '@/utils/format'
import type { MaskRegion, Template } from '@/types/models'

const props = defineProps<{
  template: Template
}>()

const boardStyle = computed(() => {
  return props.template.templateType === 'mobile_screen'
    ? { aspectRatio: '9 / 19.5' }
    : { aspectRatio: '16 / 10' }
})

function createRegionStyle(region: MaskRegion) {
  return {
    left: `${region.xRatio * 100}%`,
    top: `${region.yRatio * 100}%`,
    width: `${region.widthRatio * 100}%`,
    height: `${region.heightRatio * 100}%`
  }
}
</script>

<template>
  <div class="space-y-4">
    <div
      class="relative overflow-hidden rounded-3xl border border-slate-200 bg-slate-900 p-4"
    >
      <div
        :style="boardStyle"
        class="relative overflow-hidden rounded-2xl bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.7),_rgba(15,23,42,0.96)_60%)]"
      >
        <div class="absolute inset-0 bg-[linear-gradient(135deg,_rgba(255,255,255,0.12),_transparent_35%,_rgba(59,130,246,0.18))]" />
        <div class="absolute left-6 top-6 rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
          {{ template.imageLabel || '模板预览' }}
        </div>
        <div
          v-for="region in template.maskRegions"
          :key="region.id"
          :style="createRegionStyle(region)"
          class="absolute rounded-xl border-2 border-amber-300 bg-amber-300/20 shadow-lg shadow-amber-900/20"
        >
          <span class="absolute -top-7 left-0 rounded-lg bg-amber-300 px-2 py-1 text-xs font-medium text-slate-900">
            {{ region.name }}
          </span>
        </div>
      </div>
    </div>
    <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <div
        v-for="region in template.maskRegions"
        :key="region.id"
        class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
      >
        <div class="mb-2 flex items-center justify-between">
          <span class="font-medium text-slate-900">{{ region.name }}</span>
          <span class="text-xs uppercase tracking-wide text-slate-400">mask-region</span>
        </div>
        <p class="m-0 text-sm text-slate-500">
          x={{ formatRatio(region.xRatio) }}，y={{ formatRatio(region.yRatio) }}，
          w={{ formatRatio(region.widthRatio) }}，h={{ formatRatio(region.heightRatio) }}
        </p>
      </div>
    </div>
  </div>
</template>
