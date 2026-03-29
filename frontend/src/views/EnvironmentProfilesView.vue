<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricCard from '@/components/MetricCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  createDeviceProfile,
  createEnvironmentProfile,
  createEnvironmentVariable,
  deleteEnvironmentProfile,
  deleteEnvironmentVariable,
  listDeviceProfiles,
  listEnvironmentProfiles,
  listEnvironmentVariables,
  updateDeviceProfile,
  updateEnvironmentProfile,
  updateEnvironmentVariable
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
const savingProfile = ref(false)
const savingVariable = ref(false)
const savingDevice = ref(false)

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

const profileForm = reactive({
  name: '',
  baseUrl: '',
  description: '',
  status: 'active'
})

const variableForm = reactive({
  key: '',
  value: '',
  description: '',
  isSecret: false
})

const deviceForm = reactive({
  name: '',
  platform: 'desktop_chrome',
  width: 1440,
  height: 900,
  pixelRatio: 1,
  userAgent: '',
  isDefault: false
})

const profileStatusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' }
]

const deviceTypeOptions = [
  { label: 'Desktop Chrome', value: 'desktop_chrome' },
  { label: 'iPhone 14', value: 'mobile_ios' },
  { label: 'Android Pixel', value: 'mobile_android' },
  { label: 'Tablet', value: 'tablet' }
]

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

function resetProfileForm() {
  profileForm.name = ''
  profileForm.baseUrl = ''
  profileForm.description = ''
  profileForm.status = 'active'
}

function resetVariableForm() {
  variableForm.key = ''
  variableForm.value = ''
  variableForm.description = ''
  variableForm.isSecret = false
}

function resetDeviceForm() {
  deviceForm.name = ''
  deviceForm.platform = 'desktop_chrome'
  deviceForm.width = 1440
  deviceForm.height = 900
  deviceForm.pixelRatio = 1
  deviceForm.userAgent = ''
  deviceForm.isDefault = false
}

function openCreateProfileDialog() {
  profileDialogMode.value = 'create'
  resetProfileForm()
  profileDialogVisible.value = true
}

function openEditProfileDialog() {
  if (!selectedEnvironment.value) {
    ElMessage.warning('请先选择一个环境档案。')
    return
  }

  profileDialogMode.value = 'edit'
  profileForm.name = selectedEnvironment.value.name
  profileForm.baseUrl = selectedEnvironment.value.baseUrl
  profileForm.description = selectedEnvironment.value.description
  profileForm.status = selectedEnvironment.value.status
  profileDialogVisible.value = true
}

async function handleSaveProfile() {
  if (!profileForm.name.trim() || !profileForm.baseUrl.trim()) {
    ElMessage.warning('请补齐环境名称和基础地址。')
    return
  }

  savingProfile.value = true

  try {
    const payload = {
      name: profileForm.name.trim(),
      baseUrl: profileForm.baseUrl.trim(),
      description: profileForm.description.trim(),
      status: profileForm.status
    }

    if (profileDialogMode.value === 'create') {
      const created = await createEnvironmentProfile(payload)
      selectedEnvironmentId.value = created.id
      ElMessage.success('环境档案已创建。')
    } else if (selectedEnvironment.value) {
      await updateEnvironmentProfile(selectedEnvironment.value.id, payload)
      ElMessage.success('环境档案已更新。')
    }

    profileDialogVisible.value = false
    await loadEnvironmentData()
    await loadEnvironmentVariables(selectedEnvironmentId.value)
  } finally {
    savingProfile.value = false
  }
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
  resetVariableForm()
  variableDialogVisible.value = true
}

function openEditVariableDialog() {
  if (!selectedVariable.value) {
    ElMessage.warning('请先选择一个环境变量。')
    return
  }

  variableDialogMode.value = 'edit'
  variableForm.key = selectedVariable.value.key
  variableForm.value = selectedVariable.value.isSecret ? '' : selectedVariable.value.displayValue
  variableForm.description = selectedVariable.value.description
  variableForm.isSecret = selectedVariable.value.isSecret
  variableDialogVisible.value = true
}

async function handleSaveVariable() {
  if (!selectedEnvironment.value) {
    ElMessage.warning('当前没有可写入变量的环境档案。')
    return
  }

  if (variableDialogMode.value === 'create' && (!variableForm.key.trim() || !variableForm.value.trim())) {
    ElMessage.warning('请补齐变量键名和值。')
    return
  }

  savingVariable.value = true

  try {
    if (variableDialogMode.value === 'create') {
      await createEnvironmentVariable(selectedEnvironment.value.id, {
        key: variableForm.key.trim(),
        value: variableForm.value,
        description: variableForm.description.trim(),
        isSecret: variableForm.isSecret
      })
      ElMessage.success('环境变量已新增。')
    } else if (selectedVariable.value) {
      await updateEnvironmentVariable(selectedVariable.value.id, {
        value:
          selectedVariable.value.isSecret && !variableForm.value.trim()
            ? undefined
            : variableForm.value,
        description: variableForm.description.trim(),
        isSecret: variableForm.isSecret
      })
      ElMessage.success('环境变量已更新。')
    }

    variableDialogVisible.value = false
    await loadEnvironmentData()
    await loadEnvironmentVariables(selectedEnvironment.value.id)
  } finally {
    savingVariable.value = false
  }
}

async function handleDeleteVariable() {
  if (!selectedVariable.value) {
    ElMessage.warning('请先选择一个环境变量。')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除变量「${selectedVariable.value.key}」吗？`,
      '删除环境变量',
      {
        type: 'warning'
      }
    )
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
  resetDeviceForm()
  deviceDialogVisible.value = true
}

function openEditDeviceDialog() {
  if (!selectedDevice.value) {
    ElMessage.warning('请先选择一个设备预设。')
    return
  }

  deviceDialogMode.value = 'edit'
  deviceForm.name = selectedDevice.value.name
  deviceForm.platform = selectedDevice.value.platform
  deviceForm.width = selectedDevice.value.width
  deviceForm.height = selectedDevice.value.height
  deviceForm.pixelRatio = selectedDevice.value.pixelRatio
  deviceForm.userAgent = selectedDevice.value.userAgent ?? ''
  deviceForm.isDefault = selectedDevice.value.isDefault
  deviceDialogVisible.value = true
}

async function handleSaveDevice() {
  if (!deviceForm.name.trim() || deviceForm.width <= 0 || deviceForm.height <= 0) {
    ElMessage.warning('请补齐设备名称与有效的视口尺寸。')
    return
  }

  savingDevice.value = true

  try {
    const payload = {
      name: deviceForm.name.trim(),
      platform: deviceForm.platform,
      width: Number(deviceForm.width),
      height: Number(deviceForm.height),
      pixelRatio: Number(deviceForm.pixelRatio),
      userAgent: deviceForm.userAgent.trim() || undefined,
      isDefault: deviceForm.isDefault
    }

    if (deviceDialogMode.value === 'create') {
      const created = await createDeviceProfile(payload)
      selectedDeviceId.value = created.id
      ElMessage.success('设备预设已创建。')
    } else if (selectedDevice.value) {
      await updateDeviceProfile(selectedDevice.value.id, payload)
      ElMessage.success('设备预设已更新。')
    }

    deviceDialogVisible.value = false
    await loadEnvironmentData()
  } finally {
    savingDevice.value = false
  }
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

    <el-dialog
      v-model="profileDialogVisible"
      :title="profileDialogMode === 'create' ? '新建环境档案' : '编辑环境档案'"
      width="520px"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">环境名称</label>
          <el-input v-model="profileForm.name" />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">基础地址</label>
          <el-input v-model="profileForm.baseUrl" placeholder="https://example.test" />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">状态</label>
          <el-select
            v-model="profileForm.status"
            class="!w-full"
          >
            <el-option
              v-for="option in profileStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
          <el-input
            v-model="profileForm.description"
            :rows="3"
            type="textarea"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="profileDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingProfile"
            color="#2563eb"
            @click="handleSaveProfile"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="variableDialogVisible"
      :title="variableDialogMode === 'create' ? '新增环境变量' : '编辑环境变量'"
      width="520px"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">键名</label>
          <el-input
            v-model="variableForm.key"
            :disabled="variableDialogMode === 'edit'"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">值</label>
          <el-input
            v-model="variableForm.value"
            :placeholder="variableDialogMode === 'edit' && selectedVariable?.isSecret ? '留空表示保持原密文值' : ''"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">备注</label>
          <el-input
            v-model="variableForm.description"
            :rows="3"
            type="textarea"
          />
        </div>
        <el-switch
          v-model="variableForm.isSecret"
          active-text="密文变量"
          inactive-text="普通变量"
        />
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="variableDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingVariable"
            color="#2563eb"
            @click="handleSaveVariable"
          >
            保存变量
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deviceDialogVisible"
      :title="deviceDialogMode === 'create' ? '新建设备预设' : '编辑设备预设'"
      width="560px"
    >
      <div class="grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">设备名称</label>
          <el-input v-model="deviceForm.name" />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">设备类型</label>
          <el-select
            v-model="deviceForm.platform"
            class="!w-full"
          >
            <el-option
              v-for="option in deviceTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">像素比</label>
          <el-input-number
            v-model="deviceForm.pixelRatio"
            :min="0.5"
            :precision="2"
            :step="0.25"
            class="!w-full"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">宽度</label>
          <el-input-number
            v-model="deviceForm.width"
            :min="1"
            class="!w-full"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">高度</label>
          <el-input-number
            v-model="deviceForm.height"
            :min="1"
            class="!w-full"
          />
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">User Agent</label>
          <el-input
            v-model="deviceForm.userAgent"
            placeholder="可选"
          />
        </div>
        <div class="col-span-2">
          <el-switch
            v-model="deviceForm.isDefault"
            active-text="设为默认设备"
            inactive-text="普通设备"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="deviceDialogVisible = false">
            取消
          </el-button>
          <el-button
            :loading="savingDevice"
            color="#2563eb"
            @click="handleSaveDevice"
          >
            保存设备
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
