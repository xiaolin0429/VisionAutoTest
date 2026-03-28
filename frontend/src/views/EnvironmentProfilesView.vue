<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listDeviceProfiles, listEnvironmentProfiles } from '@/api/modules/environments'
import { useWorkspaceStore } from '@/stores/workspace'
import { formatDateTime } from '@/utils/format'
import type { DeviceProfile, EnvironmentProfile } from '@/types/models'

const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])

const metrics = computed(() => [
  {
    label: '当前工作空间',
    value: workspaceStore.currentWorkspace?.name ?? '未选择',
    hint: '所有环境与设备配置均受 X-Workspace-Id 隔离。'
  },
  {
    label: '环境档案数',
    value: environmentProfiles.value.length,
    hint: '映射 `/api/v1/environment-profiles` 资源。'
  },
  {
    label: '设备预设数',
    value: deviceProfiles.value.length,
    hint: 'MVP 先覆盖桌面与主流移动端设备。'
  }
])

onMounted(async () => {
  loading.value = true
  try {
    const [environments, devices] = await Promise.all([
      listEnvironmentProfiles(),
      listDeviceProfiles()
    ])
    environmentProfiles.value = environments
    deviceProfiles.value = devices
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :hint="metric.hint"
        :label="metric.label"
        :value="metric.value"
      />
    </div>

    <SectionCard
      description="环境档案与变量管理对应 `environment-profiles`、`environment-variables` 资源。"
      title="环境档案"
    >
      <el-table
        v-loading="loading"
        :data="environmentProfiles"
        stripe
      >
        <el-table-column
          label="名称"
          min-width="180"
          prop="name"
        />
        <el-table-column
          label="基础地址"
          min-width="260"
          prop="baseUrl"
        />
        <el-table-column
          label="变量数"
          prop="variableCount"
          width="120"
        />
        <el-table-column
          label="状态"
          width="120"
        >
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column
          label="最近更新"
          min-width="180"
        >
          <template #default="{ row }">
            {{ formatDateTime(row.updatedAt) }}
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>

    <SectionCard
      description="设备预设对应 `device-profiles` 资源，用于执行前组合环境与屏幕规格。"
      title="设备预设"
    >
      <div class="grid grid-cols-3 gap-4">
        <div
          v-for="device in deviceProfiles"
          :key="device.id"
          class="rounded-2xl border border-slate-200 bg-slate-50 p-5"
        >
          <div class="mb-4 flex items-center justify-between">
            <h4 class="m-0 text-base font-semibold text-slate-900">
              {{ device.name }}
            </h4>
            <el-tag round>{{ device.platform }}</el-tag>
          </div>
          <p class="mb-2 mt-0 text-sm text-slate-500">
            分辨率：{{ device.width }} × {{ device.height }}
          </p>
          <p class="m-0 text-sm text-slate-500">
            像素比：{{ device.pixelRatio }} · 默认设备：{{ device.isDefault ? '是' : '否' }}
          </p>
        </div>
      </div>
    </SectionCard>
  </div>
</template>
