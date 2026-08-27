<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import StepCanvasEditor from '@/components/step/canvas/StepCanvasEditor.vue'
import { createStepCanvasPreviewFixture } from '@/dev/stepCanvasFixtures'
import type { StepStructurePath } from '@/types/stepGraph'
import type { StepDraft } from '@/utils/steps'

const router = useRouter()
const fixture = createStepCanvasPreviewFixture()
const visible = ref(true)
const drafts = ref<StepDraft[]>(fixture.drafts)
const selectedPath = ref<StepStructurePath | null>('top:0')
const statusMessage = ref(
  '本地 DEV 夹具：包含条件分支、组件预览和一个待修复错误节点。'
)

function updateDrafts(nextDrafts: StepDraft[]): void {
  drafts.value = nextDrafts
}

function handleSave(nextDrafts: StepDraft[]): void {
  drafts.value = nextDrafts
  statusMessage.value = `本地保存已拦截：收到 ${nextDrafts.length} 个顶层步骤，未请求后端。`
}

function openComponentDetail(componentId: number): void {
  visible.value = false
  void router.push({
    name: 'components',
    query: { componentId: String(componentId) }
  })
}
</script>

<template>
  <main class="step-canvas-preview">
    <section class="preview-card">
      <p class="preview-kicker">DEV ONLY</p>
      <h1>StepCanvasEditor 本地可视验收</h1>
      <p>
        该入口使用真实画布和本地夹具，不加载会话、工作空间或后端数据。
        可检查分支泳道、组件只读预览、错误定位、背景、连接样式和节点样式。
      </p>
      <el-button color="#2563eb" @click="visible = true">
        打开画布
      </el-button>
    </section>

    <StepCanvasEditor
      :visible="visible"
      :user-id="9001"
      :workspace-id="9002"
      :test-case-id="9003"
      title="DEV 画布验收用例"
      test-case-code="__DEV_STEP_CANVAS__"
      :step-drafts="drafts"
      :selected-path="selectedPath"
      :templates="fixture.templates"
      :components="fixture.components"
      :component-previews="fixture.componentPreviews"
      :status-message="statusMessage"
      @update:visible="visible = $event"
      @update:selected-path="selectedPath = $event"
      @update:step-drafts="updateDrafts"
      @save="handleSave"
      @open-component="openComponentDetail"
    />
  </main>
</template>

<style scoped>
.step-canvas-preview {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 32px;
  background: #f8fafc;
}

.preview-card {
  width: min(680px, 100%);
  padding: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  color: #334155;
  background: #fff;
  box-shadow: 0 8px 24px rgb(15 23 42 / 8%);
}

.preview-card h1 {
  margin: 4px 0 12px;
  color: #0f172a;
  font-size: 24px;
}

.preview-card p {
  line-height: 1.7;
}

.preview-kicker {
  margin: 0;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
</style>
