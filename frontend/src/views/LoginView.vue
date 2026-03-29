<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { consumeAuthNotice } from '@/auth/sessionRuntime'
import { createSession } from '@/api/modules/auth'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { formatLinkupErrorMessage } from '@/utils/http'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()

const loading = ref(false)
const form = reactive({
  username: 'admin',
  password: ''
})

const redirectPath = computed(() => {
  return typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
})

async function handleSubmit() {
  loading.value = true

  try {
    const session = await createSession(form)
    authStore.setSession(session)
    await workspaceStore.bootstrap()
    const targetPath = workspaceStore.hasWorkspace ? redirectPath.value : '/workspace-empty'
    ElMessage.success(
      workspaceStore.hasWorkspace
        ? '登录成功，已进入 MVP 工作台。'
        : '登录成功，但当前账号尚未加入工作空间。'
    )
    await router.replace(targetPath)
  } catch (error) {
    const message = formatLinkupErrorMessage(error, '登录失败，请稍后重试。')
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const notice = consumeAuthNotice()
  if (notice) {
    ElMessage.warning(notice)
  }
})
</script>

<template>
  <div class="flex min-h-screen bg-slate-950">
    <div class="flex w-[54%] flex-col justify-between bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.45),_rgba(15,23,42,1)_55%)] px-16 py-14 text-white">
      <div>
        <p class="text-sm uppercase tracking-[0.3em] text-slate-300">
          VisionAutoTest
        </p>
        <h1 class="mb-5 mt-6 text-5xl font-semibold leading-tight">
          企业级跨端视觉自动化测试平台
        </h1>
          <p class="max-w-2xl text-lg leading-8 text-slate-300">
          当前前端骨架已按后端真实 API 契约接入，围绕登录、工作空间、环境、模板、用例、套件与执行详情构建 MVP 联调闭环。
          </p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
          <p class="m-0 text-sm text-slate-300">
            后端基线
          </p>
          <p class="mb-0 mt-3 text-sm leading-7 text-slate-100">
            默认对接后端 `FastAPI /api/v1`，当前联调环境基于 `PostgreSQL + Alembic`。
          </p>
        </div>
        <div class="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
          <p class="m-0 text-sm text-slate-300">
            联调准备
          </p>
          <p class="mb-0 mt-3 text-sm leading-7 text-slate-100">
            首次联调前请先在 `backend/.env` 中配置数据库连接与管理员初始密码，再执行 `cd backend && python -m app.db.bootstrap`
          </p>
        </div>
      </div>
    </div>

    <div class="flex flex-1 items-center justify-center bg-slate-100 px-8">
      <div class="w-full max-w-md rounded-[28px] bg-white p-8 shadow-soft">
        <div class="mb-8">
          <h2 class="m-0 text-3xl font-semibold text-slate-900">
            登录工作台
          </h2>
          <p class="mb-0 mt-3 text-sm leading-6 text-slate-500">
            已预填默认管理员用户名；请输入本地环境已配置的管理员密码。若登录失败，请优先确认 PostgreSQL、`.env`、bootstrap 与后端服务状态。
          </p>
        </div>

        <form
          class="space-y-5"
          @submit.prevent="handleSubmit"
        >
          <div>
            <label
              class="mb-2 block text-sm font-medium text-slate-700"
              for="login-username"
            >
              用户名
            </label>
            <el-input
              id="login-username"
              v-model="form.username"
              autocomplete="username"
              size="large"
              placeholder="请输入用户名"
            />
          </div>

          <div>
            <label
              class="mb-2 block text-sm font-medium text-slate-700"
              for="login-password"
            >
              密码
            </label>
            <el-input
              id="login-password"
              v-model="form.password"
              autocomplete="current-password"
              show-password
              size="large"
              type="password"
              placeholder="请输入密码"
            />
          </div>

          <el-button
            :loading="loading"
            class="!mt-8 !h-12 !w-full"
            color="#2563eb"
            native-type="submit"
            size="large"
          >
            登录并进入工作空间
          </el-button>
        </form>
      </div>
    </div>
  </div>
</template>
