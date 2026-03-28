<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/client'
import { deleteCurrentSession } from '@/api/modules/auth'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const loggingOut = ref(false)

const routeTitle = computed(() => String(route.meta.title ?? 'VisionAutoTest'))
const routeDescription = computed(() => String(route.meta.description ?? ''))

const selectedWorkspaceId = computed({
  get: () => workspaceStore.currentWorkspaceId ?? undefined,
  set: (value) => {
    if (typeof value === 'number') {
      workspaceStore.setCurrentWorkspace(value)
      ElMessage.success('工作空间已切换。')
    }
  }
})

async function handleLogout() {
  loggingOut.value = true

  try {
    try {
      await deleteCurrentSession()
    } catch (error) {
      const isAlreadyInvalid =
        error instanceof ApiError &&
        (error.statusCode === 401 || error.statusCode === 403)

      if (!isAlreadyInvalid) {
        const message =
          error instanceof Error ? error.message : '退出登录失败，请稍后重试。'
        ElMessage.error(message)
        return
      }
    }

    authStore.clearSession()
    workspaceStore.reset()
    await router.replace('/login')
    ElMessage.success('已退出登录。')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <header class="flex items-center justify-between gap-6 border-b border-slate-200 bg-white px-8 py-5">
    <div>
      <h2 class="m-0 text-2xl font-semibold text-slate-900">
        {{ routeTitle }}
      </h2>
      <p class="mb-0 mt-2 text-sm text-slate-500">
        {{ routeDescription }}
      </p>
    </div>

    <div class="flex items-center gap-4">
      <el-select
        v-model="selectedWorkspaceId"
        class="!w-64"
        placeholder="请选择工作空间"
      >
        <el-option
          v-for="workspace in workspaceStore.workspaces"
          :key="workspace.id"
          :label="workspace.name"
          :value="workspace.id"
        />
      </el-select>

      <div class="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-2">
        <el-avatar class="bg-brand-600">
          {{ authStore.user?.displayName?.slice(0, 1) ?? 'Q' }}
        </el-avatar>
        <div>
          <p class="m-0 text-sm font-medium text-slate-900">
            {{ authStore.user?.displayName ?? '未登录用户' }}
          </p>
          <p class="mb-0 mt-1 text-xs text-slate-400">
            {{ authStore.user?.username ?? 'anonymous' }}
          </p>
        </div>
      </div>

      <el-button
        :loading="loggingOut"
        plain
        @click="handleLogout"
      >
        退出登录
      </el-button>
    </div>
  </header>
</template>
