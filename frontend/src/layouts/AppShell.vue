<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const workspaceStore = useWorkspaceStore()

const routerViewKey = computed(() => {
  return `${route.fullPath}:${workspaceStore.currentWorkspaceId ?? 'none'}`
})

onMounted(async () => {
  if (workspaceStore.workspaces.length === 0) {
    await workspaceStore.bootstrap()
  }
})
</script>

<template>
  <div class="flex min-h-screen bg-slate-100">
    <AppSidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <AppHeader />
      <main class="flex-1 overflow-auto p-8">
        <RouterView :key="routerViewKey" />
      </main>
    </div>
  </div>
</template>
