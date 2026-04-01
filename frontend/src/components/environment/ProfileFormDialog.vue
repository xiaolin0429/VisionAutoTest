<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createEnvironmentProfile,
  updateEnvironmentProfile
} from '@/api/modules/environments'
import type { EnvironmentProfile } from '@/types/models'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  profile: EnvironmentProfile | null
}>()

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'saved', id: number): void
}>()

const saving = ref(false)

const form = reactive({
  name: '',
  baseUrl: '',
  description: '',
  status: 'active'
})

const statusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' }
]

function resetForm() {
  form.name = ''
  form.baseUrl = ''
  form.description = ''
  form.status = 'active'
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    if (props.mode === 'edit' && props.profile) {
      form.name = props.profile.name
      form.baseUrl = props.profile.baseUrl
      form.description = props.profile.description
      form.status = props.profile.status
    } else {
      resetForm()
    }
  }
)

async function handleSave() {
  if (!form.name.trim() || !form.baseUrl.trim()) {
    ElMessage.warning('请补齐环境名称和基础地址。')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      baseUrl: form.baseUrl.trim(),
      description: form.description.trim(),
      status: form.status
    }

    if (props.mode === 'create') {
      const created = await createEnvironmentProfile(payload)
      ElMessage.success('环境档案已创建。')
      emit('saved', created.id)
    } else if (props.profile) {
      await updateEnvironmentProfile(props.profile.id, payload)
      ElMessage.success('环境档案已更新。')
      emit('saved', props.profile.id)
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
    :title="mode === 'create' ? '新建环境档案' : '编辑环境档案'"
    width="520px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="space-y-4">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">环境名称</label>
        <el-input v-model="form.name" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">基础地址</label>
        <el-input v-model="form.baseUrl" placeholder="https://example.test" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">状态</label>
        <el-select v-model="form.status" class="!w-full">
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
        <el-input v-model="form.description" :rows="3" type="textarea" />
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button :loading="saving" color="#2563eb" @click="handleSave">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>
