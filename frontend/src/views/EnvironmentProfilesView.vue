<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DeviceFormDialog from '@/components/environment/DeviceFormDialog.vue'
import ProfileFormDialog from '@/components/environment/ProfileFormDialog.vue'
import VariableFormDialog from '@/components/environment/VariableFormDialog.vue'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  deleteEnvironmentProfile,
  deleteEnvironmentVariable,
  listDeviceProfiles,
  listEnvironmentProfiles,
  listEnvironmentVariables
} from '@/api/modules/environments'
import { useWorkspaceStore } from '@/stores/workspace'
import { formatDateTime } from '@/utils/format'
import type {
  DeviceProfile,
  EnvironmentProfile,
  EnvironmentVariable
} from '@/types/models'

const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const variablesLoading = ref(false)

const environmentProfiles = ref<EnvironmentProfile[]>([])
const deviceProfiles = ref<DeviceProfile[]>([])
const currentVariables = ref<EnvironmentVariable[]>([])

const selectedEnvironmentId = ref<number | null>(null)
const selectedDeviceId = ref<number | null>(null)
const selectedVariableId = ref<number | null>(null)

const profileDialogVisible = ref(false)
const variableDialogVisible = ref(false)
const deviceDialogVisible = ref(false)

const profileDialogMode = ref<'create' | 'edit'>('create')
const variableDialogMode = ref<'create' | 'edit'>('create')
const deviceDialogMode = ref<'create' | 'edit'>('create')

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

const selectedEnvironment = computed(() => {
  return environmentProfiles.value.find((item) => item.id === selectedEnvironmentId.value) ?? null
})

const selectedDevice = computed(() => {
  return deviceProfiles.value.find((item) => item.id === selectedDeviceId.value) ?? null
})

const selectedVariable = computed(() => {
  return currentVariables.value.find((item) => item.id === selectedVariableId.value) ?? null
})

async function loadEnvironmentData() {
  loading.value = true

  try {
    const [environments, devices] = await Promise.all([
      listEnvironmentProfiles(),
      listDeviceProfiles()
    ])
    environmentProfiles.value = environments
    deviceProfiles.value = devices

    if (!environments.some((item) => item.id === selectedEnvironmentId.value)) {
      selectedEnvironmentId.value = environments[0]?.id ?? null
    }

    if (!devices.some((item) => item.id === selectedDeviceId.value)) {
      selectedDeviceId.value = devices[0]?.id ?? null
    }
  } finally {
    loading.value = false
  }
}

async function loadEnvironmentVariables(environmentProfileId: number | null) {
  if (!environmentProfileId) {
    currentVariables.value = []
    selectedVariableId.value = null
    return
  }

  variablesLoading.value = true

  try {
    const items = await listEnvironmentVariables(environmentProfileId)
    currentVariables.value = items
    if (!items.some((item) => item.id === selectedVariableId.value)) {
      selectedVariableId.value = items[0]?.id ?? null
    }
  } finally {
    variablesLoading.value = false
  }
}

function openCreateProfileDialog() {
  profileDialogMode.value = 'create'
  profileDialogVisible.value = true
}

function openEditProfileDialog() {
  if (!selectedEnvironment.value) {
    ElMessage.warning('请先选择一个环境档案。')
    return
  }

  profileDialogMode.value = 'edit'
  profileDialogVisible.value = true
}

async function handleDeleteProfile() {
  if (!selectedEnvironment.value) {
    ElMessage.warning('请先选择一个环境档案。')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除环境档案「${selectedEnvironment.value.name}」吗？关联变量也会一并失效。`,
      '删除环境档案',
      {
        type: 'warning'
      }
    )
  } catch {
    return
  }

  await deleteEnvironmentProfile(selectedEnvironment.value.id)
  ElMessage.success('环境档案已删除。')
  selectedEnvironmentId.value = null
  await loadEnvironmentData()
  await loadEnvironmentVariables(selectedEnvironmentId.value)
}

function openCreateVariableDialog() {
  if (!selectedEnvironment.value) {
    ElMessage.warning('请先选择一个环境档案。')
    return
  }

  variableDialogMode.value = 'create'
  variableDialogVisible.value = true
}

function openEditVariableDialog() {
  if (!selectedVariable.value) {
    ElMessage.warning('请先选择一个环境变量。')
    return
  }

  variableDialogMode.value = 'edit'
  variableDialogVisible.value = true
}

async function handleDeleteVariable() {
  if (!selectedVariable.value) {
    ElMessage.warning('请先选择一个环境变量。')
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除变量「${selectedVariable.value.key}」吗？`, '删除环境变量', {
      type: 'warning'
    })
  } catch {
    return
  }

  await deleteEnvironmentVariable(selectedVariable.value.id)
  ElMessage.success('环境变量已删除。')
  await loadEnvironmentData()
  await loadEnvironmentVariables(selectedEnvironment.value?.id ?? null)
}

function openCreateDeviceDialog() {
  deviceDialogMode.value = 'create'
  deviceDialogVisible.value = true
}

function openEditDeviceDialog() {
  if (!selectedDevice.value) {
    ElMessage.warning('请先选择一个设备预设。')
    return
  }

  deviceDialogMode.value = 'edit'
  deviceDialogVisible.value = true
}

async function handleProfileSaved(environmentId: number) {
  profileDialogVisible.value = false
  selectedEnvironmentId.value = environmentId
  await loadEnvironmentData()
  await loadEnvironmentVariables(environmentId)
}

async function handleVariableSaved() {
  variableDialogVisible.value = false
  await loadEnvironmentData()
  await loadEnvironmentVariables(selectedEnvironment.value?.id ?? null)
}

async function handleDeviceSaved(deviceId: number) {
  deviceDialogVisible.value = false
  selectedDeviceId.value = deviceId
  await loadEnvironmentData()
}

watch(selectedEnvironmentId, async (environmentProfileId) => {
  await loadEnvironmentVariables(environmentProfileId)
})

onMounted(async () => {
  await loadEnvironmentData()
  await loadEnvironmentVariables(selectedEnvironmentId.value)
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

    <div class="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6">
      <SectionCard
        description="环境档案支持新建、编辑、删除，并可下钻维护环境变量。"
        title="环境档案"
      >
        <template #action>
          <div class="flex gap-2">
            <el-button
              plain
              @click="openEditProfileDialog"
            >
              编辑
            </el-button>
            <el-button
              color="#2563eb"
              @click="openCreateProfileDialog"
            >
              新建环境
            </el-button>
          </div>
        </template>

        <el-table
          v-loading="loading"
          :current-row-key="selectedEnvironmentId ?? undefined"
          :data="environmentProfiles"
          highlight-current-row
          row-key="id"
          stripe
          @row-click="selectedEnvironmentId = $event.id"
        >
          <el-table-column
            label="名称"
            min-width="180"
            prop="name"
          />
          <el-table-column
            label="基础地址"
            min-width="220"
            prop="baseUrl"
          />
          <el-table-column
            label="变量数"
            prop="variableCount"
            width="100"
          />
          <el-table-column
            label="状态"
            width="110"
          >
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="100"
          >
            <template #default="{ row }">
              <el-button
                link
                type="danger"
                @click.stop="selectedEnvironmentId = row.id; void handleDeleteProfile()"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </SectionCard>

      <SectionCard
        description="环境变量支持密文标记与值更新，展示值遵循后端脱敏返回。"
        title="环境变量"
      >
        <template #action>
          <div class="flex gap-2">
            <el-button
              plain
              @click="openEditVariableDialog"
            >
              编辑变量
            </el-button>
            <el-button
              color="#2563eb"
              @click="openCreateVariableDialog"
            >
              新增变量
            </el-button>
          </div>
        </template>

        <div
          v-if="selectedEnvironment"
          class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="m-0 text-base font-semibold text-slate-900">
                {{ selectedEnvironment.name }}
              </p>
              <p class="mb-0 mt-2 text-sm text-slate-500">
                {{ selectedEnvironment.baseUrl }}
              </p>
            </div>
            <StatusTag :status="selectedEnvironment.status" />
          </div>
          <p class="mb-0 mt-3 text-xs text-slate-400">
            最近更新时间：{{ formatDateTime(selectedEnvironment.updatedAt) }}
          </p>
        </div>

        <el-empty
          v-if="!selectedEnvironment"
          description="请先选择一个环境档案"
        />

        <template v-else>
          <el-table
            v-loading="variablesLoading"
            :current-row-key="selectedVariableId ?? undefined"
            :data="currentVariables"
            empty-text="当前环境暂无变量"
            highlight-current-row
            row-key="id"
            stripe
            @row-click="selectedVariableId = $event.id"
          >
            <el-table-column
              label="键名"
              min-width="180"
              prop="key"
            />
            <el-table-column
              label="展示值"
              min-width="180"
              prop="displayValue"
            />
            <el-table-column
              label="密文"
              width="90"
            >
              <template #default="{ row }">
                {{ row.isSecret ? '是' : '否' }}
              </template>
            </el-table-column>
            <el-table-column
              label="备注"
              min-width="180"
              prop="description"
            />
            <el-table-column
              label="操作"
              width="100"
            >
              <template #default="{ row }">
                <el-button
                  link
                  type="danger"
                  @click.stop="selectedVariableId = row.id; void handleDeleteVariable()"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </SectionCard>
    </div>

    <SectionCard
      description="设备预设支持新建与编辑，用于执行前组合环境与屏幕规格。"
      title="设备预设"
    >
      <template #action>
        <div class="flex gap-2">
          <el-button
            plain
            @click="openEditDeviceDialog"
          >
            编辑设备
          </el-button>
          <el-button
            color="#2563eb"
            @click="openCreateDeviceDialog"
          >
            新建设备
          </el-button>
        </div>
      </template>

      <div class="grid grid-cols-3 gap-4">
        <button
          v-for="device in deviceProfiles"
          :key="device.id"
          :class="[
            'rounded-2xl border p-5 text-left transition',
            selectedDeviceId === device.id
              ? 'border-brand-500 bg-brand-50'
              : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          ]"
          type="button"
          @click="selectedDeviceId = device.id"
        >
          <div class="mb-4 flex items-center justify-between">
            <h4 class="m-0 text-base font-semibold text-slate-900">
              {{ device.name }}
            </h4>
            <el-tag round>
              {{ device.platform }}
            </el-tag>
          </div>
          <p class="mb-2 mt-0 text-sm text-slate-500">
            分辨率：{{ device.width }} × {{ device.height }}
          </p>
          <p class="m-0 text-sm text-slate-500">
            像素比：{{ device.pixelRatio }} · 默认设备：{{ device.isDefault ? '是' : '否' }}
          </p>
          <p class="mb-0 mt-3 text-xs text-slate-400">
            更新时间：{{ formatDateTime(device.updatedAt) }}
          </p>
        </button>
      </div>
    </SectionCard>

    <ProfileFormDialog
      :mode="profileDialogMode"
      :profile="selectedEnvironment"
      :visible="profileDialogVisible"
      @saved="handleProfileSaved"
      @update:visible="profileDialogVisible = $event"
    />

    <VariableFormDialog
      :environment-profile-id="selectedEnvironment?.id ?? null"
      :mode="variableDialogMode"
      :variable="selectedVariable"
      :visible="variableDialogVisible"
      @saved="handleVariableSaved"
      @update:visible="variableDialogVisible = $event"
    />

    <DeviceFormDialog
      :device="selectedDevice"
      :mode="deviceDialogMode"
      :visible="deviceDialogVisible"
      @saved="handleDeviceSaved"
      @update:visible="deviceDialogVisible = $event"
    />
  </div>
</template>
