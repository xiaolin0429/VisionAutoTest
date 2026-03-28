<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const backTarget = computed(() => {
  return authStore.isAuthenticated ? '/dashboard' : '/login'
})

const backLabel = computed(() => {
  return authStore.isAuthenticated ? '返回工作台' : '返回登录页'
})

function goBack() {
  void router.replace(backTarget.value)
}

function goPrevious() {
  window.history.back()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-950 px-6">
    <div class="w-full max-w-3xl rounded-[32px] border border-white/10 bg-white/5 p-10 text-white shadow-soft backdrop-blur">
      <p class="m-0 text-sm uppercase tracking-[0.28em] text-slate-400">
        VisionAutoTest
      </p>
      <h1 class="mb-0 mt-6 text-6xl font-semibold">
        404
      </h1>
      <h2 class="mb-0 mt-4 text-3xl font-semibold">
        页面不存在
      </h2>
      <p class="mb-0 mt-5 max-w-2xl text-base leading-8 text-slate-300">
        你访问的页面未在当前 MVP 前端中定义，可能是地址输入错误，或目标页面仍处于后续迭代计划中。
      </p>

      <div class="mt-10 flex gap-4">
        <el-button
          color="#2563eb"
          size="large"
          @click="goBack"
        >
          {{ backLabel }}
        </el-button>
        <el-button
          plain
          size="large"
          @click="goPrevious"
        >
          返回上一页
        </el-button>
      </div>
    </div>
  </div>
</template>
