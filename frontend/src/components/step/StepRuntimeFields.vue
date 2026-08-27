<script setup lang="ts">
import type { StepDraft, StepFieldErrorGetter } from '@/utils/steps'

defineProps<{
  step: StepDraft
  getFieldError: StepFieldErrorGetter
}>()
</script>

<template>
  <div>
    <label class="mb-2 block text-sm font-medium text-slate-700">超时时间(ms)</label>
    <el-input-number v-model="step.timeoutMs" :min="1" class="!w-full" />
    <p v-if="getFieldError('timeoutMs')" class="mt-2 text-xs text-rose-600">
      {{ getFieldError('timeoutMs') }}
    </p>
  </div>
  <div>
    <label class="mb-2 block text-sm font-medium text-slate-700">重试次数</label>
    <el-input-number v-model="step.retryTimes" :min="0" class="!w-full" />
    <p v-if="getFieldError('retryTimes')" class="mt-2 text-xs text-rose-600">
      {{ getFieldError('retryTimes') }}
    </p>
  </div>
</template>
