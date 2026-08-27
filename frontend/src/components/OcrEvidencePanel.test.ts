import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OcrEvidencePanel from '@/components/OcrEvidencePanel.vue'
import type { OcrEvidenceMetadata } from '@/types/models'

function createMetadata(
  overrides: Partial<OcrEvidenceMetadata> = {}
): OcrEvidenceMetadata {
  return {
    scope: 'page',
    language: 'zh_en',
    matchedText: '提交',
    role: 'button',
    confidence: 0.96,
    score: 0.93,
    pixelRect: { x: 20, y: 30, width: 80, height: 24 },
    ratioRect: { x: 0.02, y: 0.03, width: 0.08, height: 0.024 },
    viewportCssRect: { x: 20, y: 30, width: 80, height: 24 },
    documentCssRect: { x: 20, y: 630, width: 80, height: 24 },
    actionPoint: { x: 60, y: 42 },
    actionPointMode: 'text_center',
    candidateCount: 2,
    candidates: [
      {
        rank: 1,
        matchedText: '提交',
        role: 'button',
        confidence: 0.96,
        score: 0.93,
        viewportCssRect: { x: 20, y: 30, width: 80, height: 24 },
        documentCssRect: { x: 20, y: 630, width: 80, height: 24 }
      }
    ],
    preprocessVariants: ['original', 'clahe'],
    tiles: { scanned: 2, captured: 3 },
    cache: {
      analysisHits: 1,
      analysisMisses: 2,
      snapshotHits: 0,
      snapshotMisses: 3,
      generation: 4,
      lastInvalidationReason: 'click'
    },
    revalidation: { required: true, attempted: true, passed: true },
    durationMs: { ocr: 12.4, locate: 18.8 },
    errorCode: null,
    assertion: null,
    assertionStatus: null,
    assertionScope: null,
    expectedCount: null,
    matchedCount: null,
    legacyElementScope: false,
    ...overrides
  }
}

describe('OcrEvidencePanel', (): void => {
  it('quietly renders OCR explanation fields and candidate summaries', (): void => {
    const wrapper = mount(OcrEvidencePanel, {
      props: { metadata: createMetadata() }
    })

    expect(wrapper.text()).toContain('OCR 解释')
    expect(wrapper.text()).toContain('page / zh_en')
    expect(wrapper.text()).toContain('提交 / button')
    expect(wrapper.text()).toContain('0.960 / 0.930')
    expect(wrapper.text()).toContain('候选摘要（1/2）')
    expect(wrapper.text()).toContain('original、clahe')
    expect(wrapper.text()).toContain('二次确认通过')
  })

  it.each([
    ['OCR_TARGET_NOT_FOUND', '检查目标文字、匹配方式和扫描范围'],
    ['OCR_TARGET_AMBIGUOUS', '增加角色、相对关系或 occurrence'],
    ['OCR_CONFIDENCE_LOW', '谨慎调整最低置信度或最低综合分'],
    ['OCR_ACTION_REVALIDATION_FAILED', '页面在定位后发生变化']
  ])('renders a repair hint for %s', (errorCode, expectedHint): void => {
    const wrapper = mount(OcrEvidencePanel, {
      props: {
        metadata: createMetadata({ errorCode })
      }
    })

    expect(wrapper.text()).toContain(expectedHint)
  })
})
