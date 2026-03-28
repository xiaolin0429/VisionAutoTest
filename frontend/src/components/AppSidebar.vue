<script setup lang="ts">
import { useRoute } from 'vue-router'
import { navigationItems } from '@/constants/navigation'

const route = useRoute()
</script>

<template>
  <aside class="flex w-64 flex-col bg-slate-950 px-4 py-6 text-slate-100">
    <div class="mb-8 px-3">
      <p class="mb-2 text-xs uppercase tracking-[0.24em] text-slate-400">
        VisionAutoTest
      </p>
      <h1 class="m-0 text-2xl font-semibold">
        Frontend MVP
      </h1>
      <p class="mb-0 mt-2 text-sm text-slate-400">
        围绕登录、模板、编排、执行与执行详情构建最小闭环。
      </p>
    </div>

    <el-menu
      :default-active="route.path"
      background-color="transparent"
      text-color="#cbd5e1"
      active-text-color="#ffffff"
      class="border-none"
      router
    >
      <el-menu-item
        v-for="item in navigationItems"
        :key="item.path"
        :index="item.path"
        class="!rounded-xl !px-4"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>

    <div class="mt-auto rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <p class="m-0 text-sm font-medium text-slate-200">
        当前接入
      </p>
      <p class="mb-0 mt-2 text-sm leading-6 text-slate-400">
        默认直连后端 `FastAPI /api/v1` 契约，当前页面以真实接口返回结构做聚合展示。
      </p>
    </div>
  </aside>
</template>
