<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createDeviceProfile,
  updateDeviceProfile
} from '@/api/modules/environments'
import type { DeviceProfile } from '@/types/models'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  device: DeviceProfile | null
}>()

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'saved', id: number): void
}>()

const saving = ref(false)

const form = reactive({
  name: '',
  platform: 'desktop_chrome',
  width: 1440,
  height: 900,
  pixelRatio: 1,
  userAgent: '',
  isDefault: false
})

const deviceTypeOptions = [
  { label: 'Desktop Chrome', value: 'desktop_chrome' },
  { label: 'iPhone 14', value: 'mobile_ios' },
  { label: 'Android Pixel', value: 'mobile_android' },
  { label: 'Tablet', value: 'tablet' }
]

function resetForm() {
  form.name = ''
  form.platform = 'desktop_chrome'
  form.width = 1440
  form.height = 900
  form.pixelRatio = 1
  form.userAgent = ''
  form.isDefault = false
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    if (props.mode === 'edit' && props.device) {
      form.name = props.device.name
      form.platform = props.device.platform
      form.width = props.device.width
      form.height = props.device.height
      form.pixelRatio = props.device.pixelRatio
      form.userAgent = props.device.userAgent ?? ''
      form.isDefault = props.device.isDefault
    } else {
      resetForm()
    }
  }
)

async function handleSave() {
  if (!form.name.trim() || form.width <= 0 || form.height <= 0) {
    ElMessage.warning('请补齐设备名称与有效的视口尺寸。')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      platform: form.platform,
      width: Number(form.width),
      height: Number(form.height),
      pixelRatio: Number(form.pixelRatio),
      userAgent: form.userAgent.trim() || undefined,
      isDefault: form.isDefault
    }

    if (props.mode === 'create') {
      const created = await createDeviceProfile(payload)
      ElMessage.success('设备预设已创建。')
      emit('saved', created.id)
    } else if (props.device) {
      await updateDeviceProfile(props.device.id, payload)
      ElMessage.success('设备预设已更新。')
      emit('saved', props.device.id)
    }

    emit('update:visible', false)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="mode === 'create' ? '新建设备预设' : '编辑设备预设'"
    width="560px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="grid grid-cols-2 gap-4">
      <div class="col-span-2">
        <label class="mb-2 block text-sm font-medium text-slate-700">设备名称</label>
        <el-input v-model="form.name" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">设备类型</label>
        <el-select v-model="form.platform" class="!w-full">
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
          v-model="form.pixelRatio"
          :min="0.5"
          :precision="2"
          :step="0.25"
          class="!w-full"
        />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">宽度</label>
        <el-input-number v-model="form.width" :min="1" class="!w-full" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">高度</label>
        <el-input-number v-model="form.height" :min="1" class="!w-full" />
      </div>
      <div class="col-span-2">
        <label class="mb-2 block text-sm font-medium text-slate-700">User Agent</label>
        <el-input v-model="form.userAgent" placeholder="可选" />
      </div>
      <div class="col-span-2">
        <el-switch
          v-model="form.isDefault"
          active-text="设为默认设备"
          inactive-text="普通设备"
        />
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button :loading="saving" color="#2563eb" @click="handleSave">保存设备</el-button>
      </div>
    </template>
  </el-dialog>
</template>
