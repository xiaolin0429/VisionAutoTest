<script setup lang="ts">
import { computed } from 'vue'

import {
  OCR_ACTION_POINT_OPTIONS,
  OCR_LANGUAGE_OPTIONS,
  OCR_LOCATOR_MATCH_MODE_OPTIONS,
  OCR_RELATION_TYPE_OPTIONS,
  OCR_ROLE_OPTIONS,
  OCR_TARGET_SCOPE_OPTIONS,
  validateOcrTargetDraft,
  type OcrTargetDraft,
  type OcrTargetValidationErrors
} from '@/utils/steps'

const props = withDefaults(defineProps<{
  target: OcrTargetDraft
  title?: string
  showScope?: boolean
  showActionPoint?: boolean
}>(), {
  title: 'OCR 目标',
  showScope: true,
  showActionPoint: true
})

const errors = computed(
  (): OcrTargetValidationErrors => validateOcrTargetDraft(props.target)
)

function toggleRelation(enabled: boolean): void {
  props.target.relation = enabled
    ? props.target.relation ?? {
        type: 'nearest',
        anchorText: '',
        maxDistanceRatio: 0.25
      }
    : null
}
</script>

<template>
  <div class="col-span-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
    <div class="mb-3 flex items-center justify-between gap-3">
      <strong class="text-sm text-slate-800">{{ title }}</strong>
      <span class="text-xs text-slate-500">纯 OCR，不回退 selector 或模板</span>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="col-span-2">
        <label class="mb-2 block text-sm font-medium text-slate-700">目标文字</label>
        <el-input v-model="target.text" placeholder="请输入截图中可见的目标文字" />
        <p v-if="errors.text" class="mt-2 text-xs text-rose-600">{{ errors.text }}</p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">匹配模式</label>
        <el-select v-model="target.matchMode" class="!w-full">
          <el-option
            v-for="option in OCR_LOCATOR_MATCH_MODE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <p v-if="errors.matchMode" class="mt-2 text-xs text-rose-600">
          {{ errors.matchMode }}
        </p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">匹配序号</label>
        <el-input-number v-model="target.occurrence" :min="1" class="!w-full" />
        <p v-if="errors.occurrence" class="mt-2 text-xs text-rose-600">
          {{ errors.occurrence }}
        </p>
      </div>

      <div v-if="showScope">
        <label class="mb-2 block text-sm font-medium text-slate-700">扫描范围</label>
        <el-select v-model="target.scope" class="!w-full">
          <el-option
            v-for="option in OCR_TARGET_SCOPE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <p v-if="errors.scope" class="mt-2 text-xs text-rose-600">{{ errors.scope }}</p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">语言档案</label>
        <el-select v-model="target.language" class="!w-full">
          <el-option
            v-for="option in OCR_LANGUAGE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <p v-if="errors.language" class="mt-2 text-xs text-rose-600">
          {{ errors.language }}
        </p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">角色提示</label>
        <el-select v-model="target.role" class="!w-full">
          <el-option
            v-for="option in OCR_ROLE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <p v-if="errors.role" class="mt-2 text-xs text-rose-600">{{ errors.role }}</p>
      </div>

      <div v-if="showActionPoint">
        <label class="mb-2 block text-sm font-medium text-slate-700">操作点</label>
        <el-select v-model="target.actionPoint" class="!w-full">
          <el-option
            v-for="option in OCR_ACTION_POINT_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <p v-if="errors.actionPoint" class="mt-2 text-xs text-rose-600">
          {{ errors.actionPoint }}
        </p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">最低 OCR 置信度</label>
        <el-input-number
          v-model="target.minConfidence"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.05"
          class="!w-full"
        />
        <p v-if="errors.minConfidence" class="mt-2 text-xs text-rose-600">
          {{ errors.minConfidence }}
        </p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">最低综合分</label>
        <el-input-number
          v-model="target.minScore"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.05"
          class="!w-full"
        />
        <p v-if="errors.minScore" class="mt-2 text-xs text-rose-600">
          {{ errors.minScore }}
        </p>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-slate-700">歧义分差</label>
        <el-input-number
          v-model="target.ambiguityMargin"
          :max="1"
          :min="0"
          :precision="2"
          :step="0.05"
          class="!w-full"
        />
        <p v-if="errors.ambiguityMargin" class="mt-2 text-xs text-rose-600">
          {{ errors.ambiguityMargin }}
        </p>
      </div>

      <div class="flex items-end">
        <div class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
          <el-checkbox v-model="target.caseSensitive">区分大小写</el-checkbox>
        </div>
      </div>

      <div class="col-span-2 flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2">
        <span class="text-sm text-slate-700">使用相对文字关系消歧</span>
        <el-switch
          :model-value="target.relation !== null"
          @update:model-value="toggleRelation"
        />
      </div>

      <template v-if="target.relation">
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">关系类型</label>
          <el-select v-model="target.relation.type" class="!w-full">
            <el-option
              v-for="option in OCR_RELATION_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <p v-if="errors.relationType" class="mt-2 text-xs text-rose-600">
            {{ errors.relationType }}
          </p>
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">锚点文字</label>
          <el-input v-model="target.relation.anchorText" />
          <p v-if="errors.relationAnchorText" class="mt-2 text-xs text-rose-600">
            {{ errors.relationAnchorText }}
          </p>
        </div>
        <div class="col-span-2">
          <label class="mb-2 block text-sm font-medium text-slate-700">最大距离比例</label>
          <el-input-number
            v-model="target.relation.maxDistanceRatio"
            :max="1"
            :min="0"
            :precision="2"
            :step="0.05"
            class="!w-full"
          />
          <p v-if="errors.relationMaxDistanceRatio" class="mt-2 text-xs text-rose-600">
            {{ errors.relationMaxDistanceRatio }}
          </p>
        </div>
      </template>
    </div>
  </div>
</template>
