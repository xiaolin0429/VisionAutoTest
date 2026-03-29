import { createRouter, createWebHistory } from 'vue-router'
import { ApiError } from '@/api/client'
import AppShell from '@/layouts/AppShell.vue'
import { pinia } from '@/stores/pinia'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const LoginView = () => import('@/views/LoginView.vue')
const EmptyWorkspaceView = () => import('@/views/EmptyWorkspaceView.vue')
const DashboardView = () => import('@/views/DashboardView.vue')
const EnvironmentProfilesView = () => import('@/views/EnvironmentProfilesView.vue')
const TemplatesView = () => import('@/views/TemplatesView.vue')
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

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)
  const workspaceStore = useWorkspaceStore(pinia)
  const isPublicRoute = Boolean(to.meta.public)
  const requiresWorkspace = to.meta.requiresWorkspace !== false

  if (to.path === '/login') {
    if (!authStore.isAuthenticated) {
      return true
    }

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

        authStore.clearSession()
        workspaceStore.reset()
        return true
      }
    }

    return workspaceStore.hasWorkspace ? '/dashboard' : '/workspace-empty'
  }

  if (!isPublicRoute && !authStore.isAuthenticated) {
    return {
      path: '/login',
      query: {
        redirect: to.fullPath
      }
    }
  }

  if (!isPublicRoute && authStore.isAuthenticated && workspaceStore.workspaces.length === 0) {
    try {
      await workspaceStore.bootstrap()
    } catch (error) {
      const isUnauthorized =
        error instanceof ApiError &&
        (error.statusCode === 401 || error.statusCode === 403)

      if (!isUnauthorized) {
        throw error
      }

      authStore.clearSession()
      workspaceStore.reset()
      return {
        path: '/login',
        query: {
          redirect: to.fullPath
        }
      }
    }
  }

  if (authStore.isAuthenticated && !workspaceStore.hasWorkspace && requiresWorkspace) {
    return '/workspace-empty'
  }

  if (authStore.isAuthenticated && workspaceStore.hasWorkspace && to.path === '/workspace-empty') {
    return '/dashboard'
  }

  return true
})

export default router
