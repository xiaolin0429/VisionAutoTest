<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const workspaceStore = useWorkspaceStore()
const navigationDrawerVisible = ref(false)

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
  <div class="flex min-h-screen min-w-0 bg-slate-100">
    <AppSidebar class="hidden xl:flex" />
    <div class="flex min-w-0 flex-1 flex-col">
      <AppHeader @toggle-navigation="navigationDrawerVisible = true" />
      <main class="min-w-0 flex-1 overflow-auto p-4 xl:p-8">
        <RouterView :key="routerViewKey" />
      </main>
    </div>

    <el-drawer
      v-model="navigationDrawerVisible"
      :with-header="false"
      direction="ltr"
      size="280px"
    >
      <AppSidebar
        class="h-full !w-full"
        @navigate="navigationDrawerVisible = false"
      />
    </el-drawer>
  </div>
</template>
