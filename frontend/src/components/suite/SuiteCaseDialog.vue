<script setup lang="ts">
import { computed } from 'vue'
import StatusTag from '@/components/StatusTag.vue'
import type { TestCase } from '@/types/models'

interface SuiteCaseDraftItem {
  testCaseId: number
  name: string
  status: string
  orderNo: number
}

const props = defineProps<{
  availableCasesToAdd: TestCase[]
  savingCases: boolean
  selectedCaseToAdd: number | null
  suiteCaseDrafts: SuiteCaseDraftItem[]
  visible: boolean
}>()

const emit = defineEmits<{
  (event: 'add-case'): void
  (event: 'move-case', index: number, direction: -1 | 1): void
  (event: 'remove-case', index: number): void
  (event: 'save'): void
  (event: 'update:selectedCaseToAdd', value: number | null): void
  (event: 'update:visible', value: boolean): void
}>()

const selectedCaseModel = computed({
  get: () => props.selectedCaseToAdd,
  set: (value: number | null) => emit('update:selectedCaseToAdd', value)
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="编排套件用例"
    width="780px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="mb-4 grid grid-cols-[minmax(0,1fr)_auto] gap-3">
      <el-select
        v-model="selectedCaseModel"
        class="!w-full"
        clearable
        filterable
        placeholder="选择一个测试用例加入套件"
      >
        <el-option
          v-for="item in availableCasesToAdd"
          :key="item.id"
          :label="`${item.name} (${item.code})`"
          :value="item.id"
        />
      </el-select>
      <el-button plain @click="emit('add-case')">加入套件</el-button>
    </div>

    <div class="space-y-3">
      <div
        v-for="(item, index) in suiteCaseDrafts"
        :key="item.testCaseId"
        class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 p-4"
      >
        <div>
          <p class="m-0 text-base font-semibold text-slate-900">
            {{ item.orderNo }}. {{ item.name }}
          </p>
          <p class="mb-0 mt-2 text-sm text-slate-500">测试用例 #{{ item.testCaseId }}</p>
        </div>
        <div class="flex items-center gap-2">
          <StatusTag :status="item.status" />
          <el-button plain @click="emit('move-case', index, -1)">上移</el-button>
          <el-button plain @click="emit('move-case', index, 1)">下移</el-button>
          <el-button link type="danger" @click="emit('remove-case', index)">移除</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button :loading="savingCases" color="#2563eb" @click="emit('save')">
          保存编排
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
