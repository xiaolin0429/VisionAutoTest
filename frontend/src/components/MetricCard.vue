<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  hint: string
}>()
</script>

<template>
  <div class="panel-card p-5">
    <p class="m-0 text-sm text-slate-500">
      {{ label }}
    </p>
    <p class="mb-2 mt-3 text-3xl font-semibold text-slate-900">
      {{ value }}
    </p>
    <p class="m-0 text-sm text-slate-400">
      {{ hint }}
    </p>
  </div>
</template>
