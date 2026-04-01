<script setup lang="ts">
import SectionCard from '@/components/SectionCard.vue'
import TemplateCanvas from '@/components/TemplateCanvas.vue'
import type {
  BaselineRevision,
  MaskRegion,
  TemplateEditorMode,
  TemplateOcrBlock,
  TemplateOcrPanelState,
  TemplateOcrResult,
  TemplatePreviewState,
  TemplateWorkbenchViewMode
} from '@/types/models'

interface WorkbenchViewOption {
  label: string
  value: TemplateWorkbenchViewMode
}

defineProps<{
  activeMaskRegions: MaskRegion[]
  baselinePreviewError: string
  baselinePreviewLoading: boolean
  baselinePreviewUrl: string | null
  canTriggerOcr: boolean
  currentBaselineRevision: BaselineRevision | null
  editorMode: TemplateEditorMode
  hasPendingMaskDraft: boolean
  ocrBlocks: TemplateOcrBlock[]
  ocrPanelState: TemplateOcrPanelState
  ocrSnapshot: TemplateOcrResult | null
  previewState: TemplatePreviewState
  selectedMask: MaskRegion | null
  selectedMaskId: number | null
  selectedMaskName: string
  selectedOcrResultId: string | null
  templateType: string
  workbenchImageLabel: string
  workbenchViewMode: TemplateWorkbenchViewMode
  workbenchViewOptions: ReadonlyArray<WorkbenchViewOption>
}>()

const emit = defineEmits<{
  (event: 'delete-selected-mask'): void
  (event: 'select-mask', value: number | null): void
  (event: 'select-ocr-block', value: string | null): void
  (event: 'select-view-mode', value: TemplateWorkbenchViewMode): void
  (event: 'trigger-ocr'): void
  (event: 'update:regions', value: MaskRegion[]): void
  (event: 'update:selected-mask-name', value: string): void
  (event: 'convert-ocr-result-to-mask', value: TemplateOcrBlock): void
}>()

function formatRatioValue(value: number) {
  return value.toFixed(4)
}
</script>

<template>
  <SectionCard
    description="模板页已升级为围绕真实基准图工作的前端工作台，当前阶段聚焦真实图片、Mask 编辑与 OCR/预览骨架。"
    title="模板资产工作台"
  >
    <div class="grid grid-cols-[minmax(0,1fr)_360px] gap-6">
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div>
            <p class="m-0 text-sm font-medium text-slate-700">当前工作基准</p>
            <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
              {{
                currentBaselineRevision
                  ? `当前正在围绕 v${currentBaselineRevision.revisionNo} 进行图片查看、Mask 编辑与后续 OCR 处理。`
                  : '当前模板还没有可用于工作台展示的基准版本。'
              }}
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <el-button
              v-for="option in workbenchViewOptions"
              :key="option.value"
              :plain="workbenchViewMode !== option.value"
              :type="workbenchViewMode === option.value ? 'primary' : 'default'"
              @click="emit('select-view-mode', option.value)"
            >
              {{ option.label }}
            </el-button>
          </div>
        </div>

        <TemplateCanvas
          :editable="editorMode === 'edit'"
          :image-error="baselinePreviewError"
          :image-label="workbenchImageLabel"
          :image-loading="baselinePreviewLoading"
          :image-url="baselinePreviewUrl"
          :ocr-blocks="ocrBlocks"
          :overlay-image-url="previewState.overlayImageUrl"
          :preview-state="workbenchViewMode === 'ocr' ? ocrPanelState : previewState"
          :processed-image-url="previewState.processedImageUrl"
          :regions="activeMaskRegions"
          :selected-mask-id="selectedMaskId"
          :selected-ocr-result-id="selectedOcrResultId"
          :template-type="templateType"
          :view-mode="workbenchViewMode"
          @update:regions="emit('update:regions', $event)"
          @update:selected-mask-id="emit('select-mask', $event)"
          @update:selected-ocr-result-id="emit('select-ocr-block', $event)"
        />
      </div>

      <div class="space-y-4">
        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p
            v-if="hasPendingMaskDraft"
            class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700"
          >
            当前 Mask 草稿尚未保存。切换模板、切换基准版本、离开页面前，请先保存或取消；同一基准版本内仍可切换视图查看草稿预览。
          </p>
          <p class="m-0 text-sm font-medium text-slate-700">当前模式</p>
          <p class="mb-0 mt-2 text-sm leading-6 text-slate-500">
            {{
              editorMode === 'edit'
                ? '编辑模式下可直接基于真实图片拖拽区域、缩放角点，并在右侧维护名称与删除操作。'
                : '浏览模式下可切换原图、OCR、Mask 与处理后视图，核对工作基准与区域覆盖效果。'
            }}
          </p>
        </div>

        <SectionCard
          description="OCR 结果按 template + baseline revision 唯一快照联调，重复触发会覆盖更新，不展示历史列表。"
          title="OCR 结果"
        >
          <template #action>
            <el-button
              :disabled="!canTriggerOcr"
              plain
              type="primary"
              @click="emit('trigger-ocr')"
            >
              执行 OCR 分析
            </el-button>
          </template>

          <div class="space-y-3">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
              {{ ocrPanelState.message }}
            </div>

            <div v-if="ocrSnapshot" class="grid grid-cols-2 gap-3 text-sm">
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">OCR 状态</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ ocrSnapshot.status }}
                </p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">识别引擎</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ ocrSnapshot.engineName }}
                </p>
              </div>
            </div>

            <el-empty v-if="ocrBlocks.length === 0" description="当前暂无 OCR 结果" />

            <div v-else class="space-y-3">
              <button
                v-for="result in ocrBlocks"
                :key="result.id"
                :class="[
                  'w-full rounded-2xl border p-4 text-left transition',
                  selectedOcrResultId === result.id
                    ? 'border-emerald-400 bg-emerald-50'
                    : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                ]"
                type="button"
                @click="emit('select-ocr-block', result.id)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="m-0 text-sm font-semibold text-slate-900">
                      {{ result.orderNo }}. {{ result.text || '未识别文本' }}
                    </p>
                    <p class="mb-0 mt-2 text-xs text-slate-500">
                      置信度 {{ result.confidence.toFixed(2) }}
                    </p>
                  </div>
                  <el-button
                    plain
                    size="small"
                    type="primary"
                    @click.stop="emit('convert-ocr-result-to-mask', result)"
                  >
                    转为 Mask
                  </el-button>
                </div>
              </button>
            </div>
          </div>
        </SectionCard>

        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div class="mb-4 flex items-center justify-between">
            <p class="m-0 text-sm font-medium text-slate-700">选中区域</p>
            <span v-if="selectedMask" class="text-xs text-slate-400">
              ID {{ selectedMask.id }}
            </span>
          </div>

          <template v-if="selectedMask">
            <label class="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-500">
              区域名称
            </label>
            <el-input
              :model-value="selectedMaskName"
              :disabled="editorMode !== 'edit'"
              placeholder="请输入区域名称"
              @update:model-value="emit('update:selected-mask-name', $event)"
            />

            <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">横向比例</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ formatRatioValue(selectedMask.xRatio) }}
                </p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">纵向比例</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ formatRatioValue(selectedMask.yRatio) }}
                </p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">宽度比例</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ formatRatioValue(selectedMask.widthRatio) }}
                </p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <p class="m-0 text-slate-500">高度比例</p>
                <p class="mb-0 mt-2 font-medium text-slate-900">
                  {{ formatRatioValue(selectedMask.heightRatio) }}
                </p>
              </div>
            </div>

            <el-button
              v-if="editorMode === 'edit'"
              class="!mt-4 !w-full"
              plain
              type="danger"
              @click="emit('delete-selected-mask')"
            >
              删除当前区域
            </el-button>
          </template>

          <el-empty v-else description="请选择一个 Mask" />
        </div>
      </div>
    </div>

    <el-table
      :current-row-key="selectedMaskId ?? undefined"
      :data="activeMaskRegions"
      class="!mt-6"
      highlight-current-row
      row-key="id"
      @row-click="emit('select-mask', $event.id)"
    >
      <el-table-column label="名称" min-width="200" prop="name" />
      <el-table-column label="横向比例" min-width="120">
        <template #default="{ row }">
          {{ formatRatioValue(row.xRatio) }}
        </template>
      </el-table-column>
      <el-table-column label="纵向比例" min-width="120">
        <template #default="{ row }">
          {{ formatRatioValue(row.yRatio) }}
        </template>
      </el-table-column>
      <el-table-column label="宽度比例" min-width="120">
        <template #default="{ row }">
          {{ formatRatioValue(row.widthRatio) }}
        </template>
      </el-table-column>
      <el-table-column label="高度比例" min-width="120">
        <template #default="{ row }">
          {{ formatRatioValue(row.heightRatio) }}
        </template>
      </el-table-column>
      <el-table-column label="排序" prop="sortOrder" width="120" />
    </el-table>
  </SectionCard>
</template>
