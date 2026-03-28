<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { getTestCaseDetail, listTestCases } from '@/api/modules/testCases'
import { formatDateTime } from '@/utils/format'
import type { TestCase } from '@/types/models'

const loading = ref(false)
const testCases = ref<TestCase[]>([])
const selectedCaseId = ref<number | null>(null)
const currentCase = ref<TestCase | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const items = await listTestCases()
    testCases.value = items
    selectedCaseId.value = items[0]?.id ?? null
  } finally {
    loading.value = false
  }
})

watch(
  selectedCaseId,
  async (testCaseId) => {
    if (!testCaseId) {
      currentCase.value = null
      return
    }

    loading.value = true
    try {
      currentCase.value = await getTestCaseDetail(testCaseId)
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
      description="对齐 `test-cases` 真实资源，详情页通过 `/steps` 子资源拉取步骤。"
      title="用例列表"
    >
      <div class="space-y-3">
        <button
          v-for="item in testCases"
          :key="item.id"
          :class="[
            'w-full rounded-2xl border p-4 text-left transition',
            selectedCaseId === item.id
              ? 'border-brand-500 bg-brand-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          ]"
          type="button"
          @click="selectedCaseId = item.id"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                {{ item.name }}
              </p>
              <p class="mb-0 mt-2 text-sm text-slate-500">
                {{ item.code }} · {{ item.priority }}
              </p>
            </div>
            <StatusTag :status="item.status" />
          </div>
          <p class="mb-0 mt-3 text-xs text-slate-400">
            {{ formatDateTime(item.updatedAt) }}
          </p>
        </button>
      </div>
    </SectionCard>

    <SectionCard
      description="步骤顺序从 1 开始连续，组件/模板引用与 payload 以真实后端字段聚合展示。"
      title="用例详情"
    >
      <template #action>
        <StatusTag
          v-if="currentCase"
          :status="currentCase.status"
        />
      </template>

      <div
        v-if="currentCase"
        class="space-y-6"
      >
        <div class="grid grid-cols-4 gap-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              用例编码
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentCase.code }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              用例名称
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentCase.name }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              公共组件数
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ currentCase.componentCount }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="m-0 text-sm text-slate-500">
              最近更新时间
            </p>
            <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
              {{ formatDateTime(currentCase.updatedAt) }}
            </p>
          </div>
        </div>

        <el-table
          v-loading="loading"
          :data="currentCase.steps"
          stripe
        >
          <el-table-column
            label="Step No"
            prop="stepNo"
            width="90"
          />
          <el-table-column
            label="步骤名称"
            min-width="220"
            prop="name"
          />
          <el-table-column
            label="类型"
            min-width="150"
            prop="type"
          />
          <el-table-column
            label="目标"
            min-width="220"
            prop="target"
          />
          <el-table-column
            label="备注"
            min-width="280"
            prop="note"
          />
        </el-table>
      </div>

      <el-empty
        v-else
        description="暂无用例数据"
      />
    </SectionCard>
  </div>
</template>
