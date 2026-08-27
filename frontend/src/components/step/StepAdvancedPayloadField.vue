<script setup lang="ts">
import type { StepDraft, StepFieldErrorGetter } from '@/utils/steps'

withDefaults(
  defineProps<{
    step: StepDraft
    getFieldError: StepFieldErrorGetter
    collapsible?: boolean
    open?: boolean
  }>(),
  {
    collapsible: true,
    open: false
  }
)
</script>

<template>
  <div class="col-span-2">
    <details
      v-if="collapsible"
      :open="open"
      class="rounded-2xl border border-slate-200 bg-white"
    >
      <summary class="cursor-pointer list-none px-4 py-3 text-sm font-medium text-slate-700">
        高级 payload 配置
      </summary>
      <div class="border-t border-slate-200 px-4 py-4">
        <p class="m-0 text-sm leading-6 text-slate-500">
          这里填写额外 payload JSON。已提供的结构化字段会在保存时自动覆盖同名键。
        </p>
        <el-input v-model="step.extraPayloadJson" :rows="5" class="!mt-3" type="textarea" />
        <p v-if="getFieldError('extraPayloadJson')" class="mt-2 text-xs text-rose-600">
          {{ getFieldError('extraPayloadJson') }}
        </p>
      </div>
    </details>

    <template v-else>
      <label class="mb-2 block text-sm font-medium text-slate-700">高级 payload</label>
      <p class="mb-3 mt-0 text-xs leading-5 text-slate-500">
        已提供的结构化字段会在保存时自动覆盖同名键。
      </p>
      <el-input v-model="step.extraPayloadJson" :rows="4" type="textarea" />
      <p v-if="getFieldError('extraPayloadJson')" class="mt-2 text-xs text-rose-600">
        {{ getFieldError('extraPayloadJson') }}
      </p>
    </template>
  </div>
</template>
