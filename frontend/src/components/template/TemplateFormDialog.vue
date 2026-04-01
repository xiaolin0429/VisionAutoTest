<script setup lang="ts">
import {
  matchStrategyOptions,
  templateStatusOptions,
  templateTypeOptions,
  type TemplateDialogFormState
} from '@/composables/useTemplateDialogs'

defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  form: TemplateDialogFormState
  submitting: boolean
  canSubmit: boolean
  nameError: string
  thresholdError: string
  codeError?: string
  fileError?: string
  fileName?: string
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
    :title="mode === 'create' ? '新建模板' : '编辑模板'"
    destroy-on-close
    width="560px"
    @closed="emit('closed')"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form label-position="top" @submit.prevent>
      <el-form-item v-if="mode === 'create'" :error="codeError" label="模板编码" required>
        <el-input v-model="form.templateCode" placeholder="请输入模板编码" />
      </el-form-item>

      <el-form-item :error="nameError" label="模板名称" required>
        <el-input v-model="form.templateName" placeholder="请输入模板名称" />
      </el-form-item>

      <div class="grid grid-cols-2 gap-4">
        <el-form-item label="模板类型">
          <el-select v-model="form.templateType" class="!w-full">
            <el-option
              v-for="item in templateTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="匹配策略">
          <el-select v-model="form.matchStrategy" class="!w-full">
            <el-option
              v-for="item in matchStrategyOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </div>

      <p class="mb-4 -mt-2 text-xs leading-5 text-slate-400">
        当前联调版本仅支持 `template` 与 `ocr` 两种匹配策略，且只有 `published` 模板可进入执行链路。
      </p>

      <div class="grid grid-cols-2 gap-4">
        <el-form-item :error="thresholdError" label="匹配阈值" required>
          <el-input-number
            v-model="form.thresholdValue"
            :max="1"
            :min="0"
            :precision="2"
            :step="0.01"
            class="!w-full"
          />
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="form.status" class="!w-full">
            <el-option
              v-for="item in templateStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </div>

      <el-form-item v-if="mode === 'create'" :error="fileError" label="原始文件" required>
        <input
          accept="image/*"
          class="block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600"
          type="file"
          @change="handleFileChange"
        >
        <p class="mb-0 mt-2 text-xs text-slate-400">
          {{ fileName || '请选择原始模板文件' }}
        </p>
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
          {{ mode === 'create' ? '创建模板' : '保存修改' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
