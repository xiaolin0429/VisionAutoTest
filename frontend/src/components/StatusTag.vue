<script setup lang="ts">
import { computed } from 'vue'
import { formatStatusLabel } from '@/utils/format'

const props = defineProps<{
  status: string
}>()

const tagType = computed(() => {
  const statusTypeMap: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    active: 'success',
    published: 'success',
    passed: 'success',
    running: 'warning',
    partial_failed: 'warning',
    cancelling: 'warning',
    failed: 'danger',
    error: 'danger',
    draft: 'info',
    archived: 'info',
    queued: 'info',
    cancelled: 'info',
    pending: 'info',
    skipped: 'info',
    inactive: 'info'
  }

  return statusTypeMap[props.status] ?? 'info'
})
</script>

<template>
  <el-tag
    :type="tagType"
    effect="light"
    round
  >
    {{ formatStatusLabel(status) }}
  </el-tag>
</template>
