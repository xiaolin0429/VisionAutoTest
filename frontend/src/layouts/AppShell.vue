<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()

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
        <RouterView />
      </main>
    </div>
  </div>
</template>
