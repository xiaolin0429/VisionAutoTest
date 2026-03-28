<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TemplateCanvas from '@/components/TemplateCanvas.vue'
import { getTemplateDetail, listTemplates } from '@/api/modules/templates'
import { formatDateTime } from '@/utils/format'
import type { Template } from '@/types/models'

const loading = ref(false)
const templates = ref<Template[]>([])
const selectedTemplateId = ref<number | null>(null)
const currentTemplate = ref<Template | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const items = await listTemplates()
    templates.value = items
    selectedTemplateId.value = items[0]?.id ?? null
  } finally {
    loading.value = false
  }
})

watch(
  selectedTemplateId,
  async (templateId) => {
    if (!templateId) {
      currentTemplate.value = null
      return
    }

    loading.value = true
    try {
      currentTemplate.value = await getTemplateDetail(templateId)
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="grid grid-cols-[360px_minmax(0,1fr)] gap-6">
    <SectionCard
      description="模板、基准版本与忽略区域命名均对齐 `templates`、`baseline-revisions`、`mask-regions` 资源。"
      title="模板列表"
    >
      <div class="space-y-3">
        <button
          v-for="template in templates"
          :key="template.id"
          :class="[
            'w-full rounded-2xl border p-4 text-left transition',
            selectedTemplateId === template.id
              ? 'border-brand-500 bg-brand-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          ]"
          type="button"
          @click="selectedTemplateId = template.id"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                {{ template.name }}
              </p>
              <p class="mb-0 mt-2 text-sm text-slate-500">
                {{ template.templateType }} · {{ template.code }}
              </p>
            </div>
            <StatusTag :status="template.status" />
          </div>
          <p class="mb-0 mt-3 text-sm text-slate-400">
            {{ formatDateTime(template.updatedAt) }}
          </p>
        </button>
      </div>
    </SectionCard>

    <SectionCard
      description="当前详情页以真实模板详情、基准版本和忽略区域接口聚合展示。"
      title="模板详情"
    >
      <template #action>
        <StatusTag
          v-if="currentTemplate"
          :status="currentTemplate.status"
        />
      </template>

      <div
        v-if="currentTemplate"
        class="space-y-6"
      >
        <div class="grid grid-cols-4 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              模板编码
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentTemplate.code }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              模板类型
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentTemplate.templateType }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              当前基准版本
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentTemplate.baselineVersion }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              忽略区域数
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentTemplate.maskRegions.length }}
            </p>
          </div>
        </div>

        <TemplateCanvas :template="currentTemplate" />

        <el-table :data="currentTemplate.maskRegions">
          <el-table-column
            label="名称"
            prop="name"
          />
          <el-table-column
            label="x_ratio"
            prop="xRatio"
          />
          <el-table-column
            label="y_ratio"
            prop="yRatio"
          />
          <el-table-column
            label="width_ratio"
            prop="widthRatio"
          />
          <el-table-column
            label="height_ratio"
            prop="heightRatio"
          />
          <el-table-column
            label="sort_order"
            prop="sortOrder"
          />
        </el-table>
      </div>

      <el-empty
        v-else
        description="暂无模板数据"
      />
    </SectionCard>
  </div>
</template>
