<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { deleteCurrentSession } from '@/api/modules/auth'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { formatLinkupErrorMessage } from '@/utils/http'

const router = useRouter()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const loggingOut = ref(false)

async function handleRefresh() {
  loading.value = true

  try {
    await workspaceStore.bootstrap()

    if (workspaceStore.hasWorkspace) {
      ElMessage.success('已检测到可用工作空间，正在进入工作台。')
      await router.replace('/dashboard')
      return
    }

    ElMessage.info('当前账号仍未加入任何工作空间。')
  } catch (error) {
    const message = formatLinkupErrorMessage(error, '刷新工作空间失败，请稍后重试。')
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

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
        const message = error instanceof Error ? error.message : '退出登录失败，请稍后重试。'
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
  <div class="flex min-h-[calc(100vh-10rem)] items-center justify-center">
    <div class="w-full max-w-3xl rounded-[32px] border border-slate-200 bg-white p-10 shadow-soft">
      <p class="m-0 text-sm uppercase tracking-[0.28em] text-slate-400">
        VisionAutoTest
      </p>
      <h1 class="mb-0 mt-6 text-4xl font-semibold text-slate-900">
        当前账号尚未加入工作空间
      </h1>
      <p class="mb-0 mt-5 max-w-2xl text-base leading-8 text-slate-500">
        已完成登录，但系统没有发现当前账号可访问的工作空间。为避免业务页面继续发起带工作空间上下文的接口请求，
        系统已将你引导到此页。
      </p>

      <div class="mt-8 grid grid-cols-2 gap-4">
        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p class="m-0 text-sm text-slate-500">
            当前状态
          </p>
          <p class="mb-0 mt-3 text-lg font-semibold text-slate-900">
            0 个工作空间
          </p>
        </div>
        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p class="m-0 text-sm text-slate-500">
            建议操作
          </p>
          <p class="mb-0 mt-3 text-sm leading-7 text-slate-600">
            请先确认后端已执行 `python -m app.db.bootstrap`，再初始化工作空间并将当前用户加入成员列表，或联系管理员完成分配。
          </p>
        </div>
      </div>

      <div class="mt-8 flex gap-4">
        <el-button
          :loading="loading"
          color="#2563eb"
          size="large"
          @click="handleRefresh"
        >
          重新检测工作空间
        </el-button>
        <el-button
          plain
          size="large"
          :loading="loggingOut"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </div>
  </div>
</template>
