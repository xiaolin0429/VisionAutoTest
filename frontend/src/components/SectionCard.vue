<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <section class="panel-card p-5">
    <div class="mb-5 flex items-start justify-between gap-4">
      <div>
        <h3 class="m-0 text-lg font-semibold text-slate-900">
          {{ title }}
        </h3>
        <p
          v-if="description"
          class="mb-0 mt-1 text-sm text-slate-500"
        >
          {{ description }}
        </p>
      </div>
      <slot name="action" />
    </div>
    <slot />
  </section>
</template>
