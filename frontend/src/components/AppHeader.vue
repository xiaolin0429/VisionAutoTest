<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiError, clearPersistedAuthState } from '@/api/client'
import { resetClientSessionState } from '@/auth/sessionRuntime'
import { deleteCurrentSession } from '@/api/modules/auth'
import { useAuthStore } from '@/stores/auth'
import { formatLinkupErrorMessage } from '@/utils/http'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const loggingOut = ref(false)
const emit = defineEmits<{
  (event: 'toggle-navigation'): void
}>()

const routeTitle = computed(() => String(route.meta.title ?? 'VisionAutoTest'))
const routeDescription = computed(() => {
  const descriptionMap: Record<string, string> = {
    dashboard: '掌握当前工作空间的执行健康度与待处理事项。',
    environments: '管理执行环境、变量与设备档案。',
    templates: '维护视觉模板、基准版本与忽略区域。',
    components: '维护可复用的公共步骤组件。',
    cases: '编排测试用例与业务步骤。',
    suites: '维护回归套件并检查执行组合。',
    runs: '筛选执行结果并定位失败或异常。',
    'run-detail': '查看业务结论、证据与修复动作。'
  }
  return descriptionMap[String(route.name ?? '')] ?? String(route.meta.description ?? '')
})

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
      if (authStore.hasSession) {
        await authStore.ensureSessionAvailable().catch(() => {})
      }
      await deleteCurrentSession()
    } catch (error) {
      const isAlreadyInvalid =
        error instanceof ApiError &&
        (error.statusCode === 401 || error.statusCode === 403)

      if (!isAlreadyInvalid) {
        const message = formatLinkupErrorMessage(error, '退出登录失败，请稍后重试。')
        ElMessage.error(message)
        return
      }
    }

    resetClientSessionState()
    clearPersistedAuthState()
    window.location.replace('/login')
    ElMessage.success('已退出登录。')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <header class="flex min-w-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-4 xl:gap-6 xl:px-8 xl:py-5">
    <div class="flex min-w-0 items-center gap-3">
      <el-button
        aria-label="打开导航"
        class="xl:!hidden"
        circle
        plain
        @click="emit('toggle-navigation')"
      >
        <span aria-hidden="true">☰</span>
      </el-button>
      <div class="min-w-0">
      <h2 class="m-0 truncate text-xl font-semibold text-slate-900 xl:text-2xl">
        {{ routeTitle }}
      </h2>
      <p class="mb-0 mt-2 hidden truncate text-sm text-slate-500 2xl:block">
        {{ routeDescription }}
      </p>
      </div>
    </div>

    <div class="flex min-w-0 items-center gap-2 xl:gap-4">
      <el-select
        v-model="selectedWorkspaceId"
        class="!w-44 xl:!w-64"
        :disabled="workspaceStore.bootstrapStatus === 'loading' || workspaceStore.workspaces.length === 0"
        :loading="workspaceStore.bootstrapStatus === 'loading'"
        placeholder="请选择工作空间"
      >
        <el-option
          v-for="workspace in workspaceStore.workspaces"
          :key="workspace.id"
          :label="workspace.name"
          :value="workspace.id"
        />
      </el-select>

      <div class="hidden items-center gap-3 rounded-2xl border border-slate-200 px-4 py-2 lg:flex">
        <el-avatar class="bg-brand-600">
          {{ authStore.user?.displayName?.slice(0, 1) ?? 'Q' }}
        </el-avatar>
        <div class="hidden 2xl:block">
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
