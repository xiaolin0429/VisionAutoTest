<script setup lang="ts">
import { formatDateTime } from '@/utils/format'
import type { Template } from '@/types/models'

defineProps<{
  currentTemplate: Template
  detailBaselineVersionLabel: string
}>()
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-4 gap-4">
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">模板编码</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ currentTemplate.code }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">模板名称</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ currentTemplate.name }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">模板类型</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ currentTemplate.templateType }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">当前工作基准版本</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ detailBaselineVersionLabel }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-4 gap-4">
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">匹配策略</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ currentTemplate.matchStrategy }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">匹配阈值</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ currentTemplate.thresholdValue.toFixed(2) }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">创建时间</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ formatDateTime(currentTemplate.createdAt) }}
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p class="m-0 text-sm text-slate-500">更新时间</p>
        <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
          {{ formatDateTime(currentTemplate.updatedAt) }}
        </p>
      </div>
    </div>
  </div>
</template>
