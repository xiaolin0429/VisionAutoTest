<script setup lang="ts">
defineProps<{
  form: {
    code: string
    name: string
    status: string
    description: string
  }
  mode: 'create' | 'edit'
  savingSuite: boolean
  statusOptions: Array<{ label: string; value: string }>
  visible: boolean
}>()

const emit = defineEmits<{
  (event: 'submit'): void
  (event: 'update:visible', value: boolean): void
}>()
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="mode === 'create' ? '新建测试套件' : '编辑测试套件'"
    width="560px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">套件编码</label>
        <el-input v-model="form.code" :disabled="mode === 'edit'" />
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
      <div class="col-span-2">
        <label class="mb-2 block text-sm font-medium text-slate-700">套件名称</label>
        <el-input v-model="form.name" />
      </div>
      <div class="col-span-2">
        <label class="mb-2 block text-sm font-medium text-slate-700">说明</label>
        <el-input v-model="form.description" :rows="4" type="textarea" />
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button :loading="savingSuite" color="#2563eb" @click="emit('submit')">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>
