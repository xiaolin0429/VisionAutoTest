<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createEnvironmentVariable,
  updateEnvironmentVariable
} from '@/api/modules/environments'
import type { EnvironmentVariable } from '@/types/models'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  environmentProfileId: number | null
  variable: EnvironmentVariable | null
}>()

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'saved'): void
}>()

const saving = ref(false)

const form = reactive({
  key: '',
  value: '',
  description: '',
  isSecret: false
})

function resetForm() {
  form.key = ''
  form.value = ''
  form.description = ''
  form.isSecret = false
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    if (props.mode === 'edit' && props.variable) {
      form.key = props.variable.key
      form.value = props.variable.isSecret ? '' : props.variable.displayValue
      form.description = props.variable.description
      form.isSecret = props.variable.isSecret
    } else {
      resetForm()
    }
  }
)

async function handleSave() {
  if (!props.environmentProfileId) {
    ElMessage.warning('当前没有可写入变量的环境档案。')
    return
  }

  if (props.mode === 'create' && (!form.key.trim() || !form.value.trim())) {
    ElMessage.warning('请补齐变量键名和值。')
    return
  }

  saving.value = true
  try {
    if (props.mode === 'create') {
      await createEnvironmentVariable(props.environmentProfileId, {
        key: form.key.trim(),
        value: form.value,
        description: form.description.trim(),
        isSecret: form.isSecret
      })
      ElMessage.success('环境变量已新增。')
    } else if (props.variable) {
      await updateEnvironmentVariable(props.variable.id, {
        value:
          props.variable.isSecret && !form.value.trim()
            ? undefined
            : form.value,
        description: form.description.trim(),
        isSecret: form.isSecret
      })
      ElMessage.success('环境变量已更新。')
    }

    emit('update:visible', false)
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="mode === 'create' ? '新增环境变量' : '编辑环境变量'"
    width="520px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="space-y-4">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">键名</label>
        <el-input v-model="form.key" :disabled="mode === 'edit'" />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">值</label>
        <el-input
          v-model="form.value"
          :placeholder="mode === 'edit' && variable?.isSecret ? '留空表示保持原密文值' : ''"
        />
      </div>
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">备注</label>
        <el-input v-model="form.description" :rows="3" type="textarea" />
      </div>
      <el-switch
        v-model="form.isSecret"
        active-text="密文变量"
        inactive-text="普通变量"
      />
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button :loading="saving" color="#2563eb" @click="handleSave">保存变量</el-button>
      </div>
    </template>
  </el-dialog>
</template>
