<script setup lang="ts">
import { computed } from 'vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { templateStatusOptions, templateTypeOptions } from '@/composables/useTemplateDialogs'
import { formatDateTime } from '@/utils/format'
import type { ExecutionReadinessIssue, Template } from '@/types/models'

const props = defineProps<{
  templates: Template[]
  selectedTemplateId: number | null
  listLoading: boolean
  listError: string
  listEmptyDescription: string
  keyword: string
  status: string
  templateType: string
  readinessIssuesByTemplateId: Record<number, ExecutionReadinessIssue[]>
}>()

const emit = defineEmits<{
  (event: 'create'): void
  (event: 'retry'): void
  (event: 'search'): void
  (event: 'reset'): void
  (event: 'select', templateId: number): void
  (event: 'update:keyword', value: string): void
  (event: 'update:status', value: string): void
  (event: 'update:templateType', value: string): void
}>()

const keywordModel = computed({
  get: () => props.keyword,
  set: (value: string) => emit('update:keyword', value)
})

const statusModel = computed({
  get: () => props.status,
  set: (value: string) => emit('update:status', value)
})

const templateTypeModel = computed({
  get: () => props.templateType,
  set: (value: string) => emit('update:templateType', value)
})
</script>

<template>
  <SectionCard
    description="模板、基准版本与忽略区域命名均对齐 `templates`、`baseline-revisions`、`mask-regions` 资源。"
    title="模板列表"
  >
    <template #action>
      <el-button color="#2563eb" @click="emit('create')">新建模板</el-button>
    </template>

    <div class="mb-4 space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_140px_140px]">
        <el-input
          v-model="keywordModel"
          clearable
          placeholder="按模板编码或名称筛选"
          @keyup.enter="emit('search')"
        />
        <el-select v-model="statusModel" clearable placeholder="全部状态">
          <el-option
            v-for="item in templateStatusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="templateTypeModel" clearable placeholder="全部类型">
          <el-option
            v-for="item in templateTypeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </div>
      <div class="flex justify-end gap-3">
        <el-button plain @click="emit('reset')">重置</el-button>
        <el-button color="#2563eb" @click="emit('search')">查询</el-button>
      </div>
    </div>

    <div v-if="listError" class="panel-muted p-5">
      <p class="m-0 text-sm font-medium text-slate-700">模板列表加载失败</p>
      <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
        {{ listError }}
      </p>
      <el-button class="!mt-4" plain @click="emit('retry')">重试</el-button>
    </div>

    <div v-else-if="listLoading" v-loading="true" class="min-h-[240px]" />

    <el-empty v-else-if="templates.length === 0" :description="listEmptyDescription">
      <el-button color="#2563eb" @click="emit('create')">立即新建模板</el-button>
    </el-empty>

    <div v-else class="space-y-3">
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
        @click="emit('select', template.id)"
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
        <p
          v-if="props.readinessIssuesByTemplateId[template.id]?.length"
          class="mb-0 mt-2 text-xs text-amber-700"
        >
          {{ props.readinessIssuesByTemplateId[template.id][0]?.message }}
        </p>
      </button>
    </div>
  </SectionCard>
</template>
