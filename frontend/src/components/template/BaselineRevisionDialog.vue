<script setup lang="ts">
import type { BaselineRevisionFormState } from '@/composables/useTemplateDialogs'

defineProps<{
  visible: boolean
  form: BaselineRevisionFormState
  fileName: string
  submitting: boolean
  canSubmit: boolean
  actionLabel: string
}>()

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'submit'): void
  (event: 'file-change', value: File | null): void
  (event: 'closed'): void
}>()

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  emit('file-change', input.files?.[0] ?? null)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    destroy-on-close
    title="新增基准版本"
    width="560px"
    @closed="emit('closed')"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form label-position="top" @submit.prevent>
      <el-form-item label="基准文件">
        <input
          accept="image/*"
          class="block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600"
          type="file"
          @change="handleFileChange"
        >
        <p class="mb-0 mt-2 text-xs text-slate-400">
          {{ fileName || '请选择新的基准文件' }}
        </p>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" placeholder="请输入本次基准版本备注" />
      </el-form-item>

      <el-form-item label="设为当前版本">
        <el-checkbox v-model="form.isCurrent">上传后立即设为当前版本</el-checkbox>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button
          :disabled="!canSubmit"
          :loading="submitting"
          color="#2563eb"
          @click="emit('submit')"
        >
          {{ actionLabel }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
