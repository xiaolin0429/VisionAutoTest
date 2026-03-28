<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppErrorStore } from '@/stores/appError'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'

const router = useRouter()
const authStore = useAuthStore()
const appErrorStore = useAppErrorStore()

const fallbackRoute = computed(() => {
  return authStore.isAuthenticated ? '/dashboard' : '/login'
})

function clearAndReturn() {
  appErrorStore.clearError()
  void router.replace(fallbackRoute.value)
}

function reloadPage() {
  appErrorStore.clearError()
  window.location.reload()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-950 px-6">
    <div class="w-full max-w-4xl rounded-[32px] border border-white/10 bg-white/5 p-10 text-white shadow-soft backdrop-blur">
      <p class="m-0 text-sm uppercase tracking-[0.28em] text-slate-400">
        VisionAutoTest
      </p>
      <h1 class="mb-0 mt-6 text-4xl font-semibold">
        应用发生异常
      </h1>
      <p class="mb-0 mt-5 max-w-3xl text-base leading-8 text-slate-300">
        当前页面渲染或路由切换过程中出现未处理错误。为了避免工作台进入不可恢复状态，系统已将你导向异常页。
      </p>

      <div class="mt-8 grid grid-cols-2 gap-4">
        <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <p class="m-0 text-sm text-slate-400">
            错误标题
          </p>
          <p class="mb-0 mt-3 text-lg font-semibold text-white">
            {{ appErrorStore.currentError?.title ?? '未知异常' }}
          </p>
        </div>
        <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <p class="m-0 text-sm text-slate-400">
            触发来源
          </p>
          <p class="mb-0 mt-3 text-lg font-semibold text-white">
            {{ appErrorStore.currentError?.source ?? 'unknown' }}
          </p>
        </div>
      </div>

      <div class="mt-4 rounded-2xl border border-white/10 bg-slate-900/70 p-5">
        <p class="m-0 text-sm text-slate-400">
          错误信息
        </p>
        <p class="mb-0 mt-3 text-base leading-7 text-slate-200">
          {{ appErrorStore.currentError?.message ?? '暂无错误详情。' }}
        </p>
      </div>

      <div
        v-if="appErrorStore.currentError?.detail"
        class="mt-4 rounded-2xl border border-white/10 bg-slate-950 p-5"
      >
        <p class="m-0 text-sm text-slate-400">
          调试详情
        </p>
        <pre class="mb-0 mt-3 overflow-auto whitespace-pre-wrap break-all text-xs leading-6 text-slate-300">{{ appErrorStore.currentError.detail }}</pre>
      </div>

      <p class="mb-0 mt-4 text-sm text-slate-400">
        记录时间：{{ appErrorStore.currentError ? formatDateTime(appErrorStore.currentError.timestamp) : '--' }}
      </p>

      <div class="mt-8 flex gap-4">
        <el-button
          color="#2563eb"
          size="large"
          @click="clearAndReturn"
        >
          返回安全页面
        </el-button>
        <el-button
          plain
          size="large"
          @click="reloadPage"
        >
          刷新应用
        </el-button>
      </div>
    </div>
  </div>
</template>
