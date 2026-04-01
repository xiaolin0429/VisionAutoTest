<script setup lang="ts">
import SectionCard from '@/components/SectionCard.vue'
import { formatDateTime } from '@/utils/format'
import type { BaselineRevision } from '@/types/models'

const props = defineProps<{
  baselineRevisions: BaselineRevision[]
  selectedBaselineRevisionId: number | null
  mediaObjectNameCache: Record<number, string>
}>()

const emit = defineEmits<{
  (event: 'select', revisionId: number): void
}>()

function resolveMediaObjectLabel(mediaObjectId: number) {
  return props.mediaObjectNameCache[mediaObjectId] ?? `媒体对象 #${mediaObjectId}`
}
</script>

<template>
  <SectionCard
    description="新增基准版本会自动上传媒体对象，并以当前模板上下文追加新的 baseline revision。"
    title="基准版本"
  >
    <template #action>
      <el-select
        :model-value="selectedBaselineRevisionId ?? undefined"
        class="!w-72"
        placeholder="请选择工作基准版本"
        @change="emit('select', Number($event))"
      >
        <el-option
          v-for="revision in baselineRevisions"
          :key="revision.id"
          :label="`v${revision.revisionNo} · ${revision.isCurrent ? '当前基准' : '历史基准'}`"
          :value="revision.id"
        />
      </el-select>
    </template>

    <el-table
      :current-row-key="selectedBaselineRevisionId ?? undefined"
      :data="baselineRevisions"
      empty-text="当前模板尚未记录基准版本"
      highlight-current-row
      row-key="id"
      stripe
      @row-click="emit('select', $event.id)"
    >
      <el-table-column label="版本号" min-width="100">
        <template #default="{ row }">v{{ row.revisionNo }}</template>
      </el-table-column>
      <el-table-column label="来源" min-width="120" prop="sourceType" />
      <el-table-column label="当前版本" min-width="120">
        <template #default="{ row }">
          <el-tag :type="row.isCurrent ? 'success' : 'info'" round>
            {{ row.isCurrent ? '当前版本' : '历史版本' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="200">
        <template #default="{ row }">
          {{ row.remark || '--' }}
        </template>
      </el-table-column>
      <el-table-column label="媒体对象" min-width="180">
        <template #default="{ row }">
          {{ resolveMediaObjectLabel(row.mediaObjectId) }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.createdAt) }}
        </template>
      </el-table-column>
    </el-table>
  </SectionCard>
</template>
