<script setup lang="ts">
import { computed } from 'vue'
import type { OcrEvidenceMetadata, OcrRect } from '@/types/models'

const props = defineProps<{
  metadata: OcrEvidenceMetadata
}>()

const repairHint = computed((): string | null => {
  switch (props.metadata.errorCode) {
    case 'OCR_TARGET_NOT_FOUND':
      return '检查目标文字、匹配方式和扫描范围；目标在视口外时可改用整页范围。'
    case 'OCR_TARGET_AMBIGUOUS':
      return '增加角色、相对关系或 occurrence，确保最高候选与其他候选有明确分差。'
    case 'OCR_CONFIDENCE_LOW':
      return '先检查页面清晰度和语言档案，再按候选分数谨慎调整最低置信度或最低综合分。'
    case 'OCR_ACTION_REVALIDATION_FAILED':
    case 'OCR_ACTION_VERIFICATION_FAILED':
      return '页面在定位后发生变化；增加稳定等待、缩小扫描范围，或让目标在动作前保持可见。'
    default:
      return null
  }
})

function formatScore(value: number | null): string {
  return value === null ? '--' : value.toFixed(3)
}

function formatDuration(value: number): string {
  return `${value.toFixed(value < 10 ? 2 : 1)} ms`
}

function formatRect(rect: OcrRect | null, ratio = false): string {
  if (!rect) {
    return '--'
  }
  const digits = ratio ? 4 : 1
  return [
    `x ${rect.x.toFixed(digits)}`,
    `y ${rect.y.toFixed(digits)}`,
    `w ${rect.width.toFixed(digits)}`,
    `h ${rect.height.toFixed(digits)}`
  ].join(' · ')
}

function formatRevalidation(metadata: OcrEvidenceMetadata): string {
  if (!metadata.revalidation.required) {
    return '无需二次确认'
  }
  if (!metadata.revalidation.attempted) {
    return '未进入二次确认'
  }
  return metadata.revalidation.passed ? '二次确认通过' : '二次确认失败'
}
</script>

<template>
  <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
    <div class="flex items-center justify-between gap-3">
      <p class="m-0 text-sm font-medium text-slate-700">OCR 解释</p>
      <span
        v-if="metadata.errorCode"
        class="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800"
      >
        {{ metadata.errorCode }}
      </span>
    </div>

    <div class="mt-3 grid grid-cols-4 gap-3 text-xs">
      <div>
        <p class="m-0 text-slate-400">范围 / 语言</p>
        <p class="mb-0 mt-1 text-slate-700">{{ metadata.scope ?? '--' }} / {{ metadata.language ?? '--' }}</p>
      </div>
      <div>
        <p class="m-0 text-slate-400">命中文字 / 角色</p>
        <p class="mb-0 mt-1 break-all text-slate-700">{{ metadata.matchedText ?? '--' }} / {{ metadata.role ?? '--' }}</p>
      </div>
      <div>
        <p class="m-0 text-slate-400">置信度 / 综合分</p>
        <p class="mb-0 mt-1 text-slate-700">{{ formatScore(metadata.confidence) }} / {{ formatScore(metadata.score) }}</p>
      </div>
      <div>
        <p class="m-0 text-slate-400">候选 / 分片</p>
        <p class="mb-0 mt-1 text-slate-700">{{ metadata.candidateCount }} / {{ metadata.tiles.scanned }}</p>
      </div>
    </div>

    <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
      <div class="rounded-lg border border-slate-200 bg-white p-3">
        <p class="m-0 text-slate-400">像素 / 比例坐标</p>
        <p class="mb-0 mt-1 text-slate-700">{{ formatRect(metadata.pixelRect) }}</p>
        <p class="mb-0 mt-1 text-slate-500">{{ formatRect(metadata.ratioRect, true) }}</p>
      </div>
      <div class="rounded-lg border border-slate-200 bg-white p-3">
        <p class="m-0 text-slate-400">视口 / 文档坐标</p>
        <p class="mb-0 mt-1 text-slate-700">{{ formatRect(metadata.viewportCssRect) }}</p>
        <p class="mb-0 mt-1 text-slate-500">{{ formatRect(metadata.documentCssRect) }}</p>
      </div>
    </div>

    <div class="mt-3 grid grid-cols-3 gap-3 text-xs text-slate-600">
      <p class="m-0">
        OCR / 定位耗时：
        {{ formatDuration(metadata.durationMs.ocr) }} / {{ formatDuration(metadata.durationMs.locate) }}
      </p>
      <p class="m-0">
        Cache：
        A {{ metadata.cache.analysisHits }}/{{ metadata.cache.analysisMisses }} ·
        S {{ metadata.cache.snapshotHits }}/{{ metadata.cache.snapshotMisses }}
      </p>
      <p class="m-0">{{ formatRevalidation(metadata) }}</p>
    </div>

    <p
      v-if="metadata.preprocessVariants.length > 0"
      class="mb-0 mt-3 text-xs text-slate-500"
    >
      预处理：{{ metadata.preprocessVariants.join('、') }}
    </p>

    <div
      v-if="metadata.candidates.length > 0"
      class="mt-3"
    >
      <p class="mb-2 mt-0 text-xs text-slate-400">候选摘要（{{ metadata.candidates.length }}/{{ metadata.candidateCount }}）</p>
      <div class="space-y-1">
        <p
          v-for="candidate in metadata.candidates"
          :key="candidate.rank"
          class="m-0 rounded-lg bg-white px-3 py-2 text-xs text-slate-600"
        >
          #{{ candidate.rank }} {{ candidate.matchedText }} · {{ candidate.role }} ·
          confidence {{ formatScore(candidate.confidence) }} · score {{ formatScore(candidate.score) }}
        </p>
      </div>
    </div>

    <p
      v-if="repairHint"
      class="mb-0 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800"
    >
      修复提示：{{ repairHint }}
    </p>
  </div>
</template>
