import { createRouter, createWebHistory } from 'vue-router'
import { ApiError, clearPersistedAuthState } from '@/api/client'
import AppShell from '@/layouts/AppShell.vue'
import {
  queueAuthNotice,
  resetClientSessionState,
  resolveSessionLifecycleMessage
} from '@/auth/sessionRuntime'
import { pinia } from '@/stores/pinia'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const LoginView = () => import('@/views/LoginView.vue')
const EmptyWorkspaceView = () => import('@/views/EmptyWorkspaceView.vue')
const DashboardView = () => import('@/views/DashboardView.vue')
const EnvironmentProfilesView = () => import('@/views/EnvironmentProfilesView.vue')
const TemplatesView = () => import('@/views/TemplatesView.vue')
const ComponentsView = () => import('@/views/ComponentsView.vue')
const TestCasesView = () => import('@/views/TestCasesView.vue')
const TestSuitesView = () => import('@/views/TestSuitesView.vue')
const TestRunsView = () => import('@/views/TestRunsView.vue')
const RunDetailView = () => import('@/views/RunDetailView.vue')
const ErrorStateView = () => import('@/views/ErrorStateView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: {
        public: true,
        title: '登录页',
        description: '建立会话并进入工作空间。'
      }
    },
    {
      path: '/error',
      name: 'error-state',
      component: ErrorStateView,
      meta: {
        public: true,
        title: '异常页',
        description: '展示全局运行时异常并提供恢复入口。'
      }
    },
    {
      path: '/',
      component: AppShell,
      children: [
        {
          path: '',
          redirect: '/dashboard'
        },
        {
          path: '/dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: {
            title: '工作台',
            description: '汇总当前工作空间的模板、套件、执行与待办。'
          }
        },
        {
          path: '/workspace-empty',
          name: 'workspace-empty',
          component: EmptyWorkspaceView,
          meta: {
            title: '工作空间初始化',
            description: '当前账号尚未加入任何工作空间。',
            requiresWorkspace: false
          }
        },
        {
          path: '/environments',
          name: 'environments',
          component: EnvironmentProfilesView,
          meta: {
            title: '环境配置',
            description: '管理 MVP 所需的环境档案与设备预设。'
          }
        },
        {
          path: '/templates',
          name: 'templates',
          component: TemplatesView,
          meta: {
            title: '模板管理',
            description: '查看视觉模板、基准版本与忽略区域比例。'
          }
        },
        {
          path: '/components',
          name: 'components',
          component: ComponentsView,
          meta: {
            title: '组件管理',
            description: '维护可复用组件及其步骤编排。'
          }
        },
        {
          path: '/cases',
          name: 'cases',
          component: TestCasesView,
          meta: {
            title: '用例编辑',
            description: '编排测试步骤并约束变量占位符规范。'
          }
        },
        {
          path: '/suites',
          name: 'suites',
          component: TestSuitesView,
          meta: {
            title: '套件管理',
            description: '维护回归套件，并触发异步执行批次。'
          }
        },
        {
          path: '/runs',
          name: 'runs',
          component: TestRunsView,
          meta: {
            title: '执行记录',
            description: '查看 test-runs 状态并进入执行详情。'
          }
        },
        {
          path: '/runs/:testRunId',
          name: 'run-detail',
          component: RunDetailView,
          meta: {
            title: '执行详情',
            description: '按 test-run 聚合查看 case-runs、step-results 与执行汇总。'
          }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
      meta: {
        public: true,
        title: '404',
        description: '页面不存在。'
      }
    }
  ]
})

function createLoginRedirect(fullPath: string) {
  // @param fullPath Protected route the user originally tried to access.
  // @returns A router location object that preserves the intended post-login redirect target.
  return {
    path: '/login',
    query: {
      redirect: fullPath
    }
  }
}

async function ensureRouteSession(fullPath: string) {
  // @param fullPath Current protected route used to build the fallback login redirect.
  // @returns Null when the stored session is still usable, otherwise a login redirect target.
  const authStore = useAuthStore(pinia)

  try {
    // Route guards do not perform login; they only verify that an already persisted
    // session can still be refreshed and resolved into a valid current session.
    await authStore.bootstrapStoredSession()
    return null
  } catch (error) {
    if (error instanceof ApiError) {
      const isLifecycleError = [
        'REFRESH_TOKEN_EXPIRED',
        'REFRESH_TOKEN_REVOKED',
        'REFRESH_TOKEN_INVALID',
        'TOKEN_REVOKED',
        'SESSION_NOT_FOUND'
      ].includes(error.code)

      if (isLifecycleError) {
        resetClientSessionState()
        clearPersistedAuthState()
        queueAuthNotice(resolveSessionLifecycleMessage(error))
        return createLoginRedirect(fullPath)
      }
    }

    throw error
  }
}

router.beforeEach(async (to) => {
  // @param to Target route being entered.
  // @returns `true` to continue navigation or a redirect target when session/workspace recovery is required.
  const authStore = useAuthStore(pinia)
  const workspaceStore = useWorkspaceStore(pinia)
  const isPublicRoute = Boolean(to.meta.public)
  const requiresWorkspace = to.meta.requiresWorkspace !== false

  // Login is handled as a dedicated branch because it must support both first entry
  // and "session exists but should not see login again" recovery behavior.
  if (to.path === '/login') {
    if (!authStore.hasSession) {
      return true
    }

    const sessionRedirect = await ensureRouteSession(
      typeof to.query.redirect === 'string' ? to.query.redirect : '/dashboard'
    )
    if (sessionRedirect) {
      return true
    }

    // Workspace bootstrap only happens after session validation so protected resource
    // requests never run with a stale token during page entry.
    if (workspaceStore.workspaces.length === 0) {
      try {
        await workspaceStore.bootstrap()
      } catch (error) {
        const isUnauthorized =
          error instanceof ApiError &&
          (error.statusCode === 401 || error.statusCode === 403)

        if (!isUnauthorized) {
          throw error
        }

        resetClientSessionState()
        clearPersistedAuthState()
        queueAuthNotice('当前会话已失效，需要重新登录。')
        return true
      }
    }

    return workspaceStore.hasWorkspace ? '/dashboard' : '/workspace-empty'
  }

  if (!isPublicRoute && !authStore.hasSession) {
    return createLoginRedirect(to.fullPath)
  }

  if (!isPublicRoute && authStore.hasSession) {
    const sessionRedirect = await ensureRouteSession(to.fullPath)
    if (sessionRedirect) {
      return sessionRedirect
    }
  }

  if (!isPublicRoute && authStore.hasSession && workspaceStore.workspaces.length === 0) {
    try {
      await workspaceStore.bootstrap()
    } catch (error) {
      const isUnauthorized =
        error instanceof ApiError &&
        (error.statusCode === 401 || error.statusCode === 403)

      if (!isUnauthorized) {
        throw error
      }

      resetClientSessionState()
      clearPersistedAuthState()
      queueAuthNotice('当前会话已失效，需要重新登录。')
      return createLoginRedirect(to.fullPath)
    }
  }

  // `workspace-empty` is an explicit sink route for authenticated users without any
  // accessible workspace. Keeping it separate avoids redirect loops in normal pages.
  if (authStore.hasSession && !workspaceStore.hasWorkspace && requiresWorkspace) {
    return '/workspace-empty'
  }

  if (authStore.hasSession && workspaceStore.hasWorkspace && to.path === '/workspace-empty') {
    return '/dashboard'
  }

  return true
})

export default router
