import ElementPlus from 'element-plus'
import {
  flushPromises,
  mount,
  type VueWrapper
} from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StepCanvasBackgroundControl from './StepCanvasBackgroundControl.vue'
import type { StepGraphBackgroundPreference } from '@/types/stepGraph'

const mountedWrappers: VueWrapper[] = []

function createPreference(
  kind: StepGraphBackgroundPreference['kind'] = 'grid'
): StepGraphBackgroundPreference {
  return {
    kind,
    color: '#f8fafc',
    imageFit: 'cover',
    imageOpacity: 0.65,
    imageFixed: true
  }
}

function mountControl(
  preference: StepGraphBackgroundPreference = createPreference()
): VueWrapper {
  const wrapper = mount(StepCanvasBackgroundControl, {
    attachTo: document.body,
    props: {
      preference
    },
    global: {
      plugins: [ElementPlus]
    }
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

async function settlePanel(): Promise<void> {
  await flushPromises()
}

function getTrigger(wrapper: VueWrapper) {
  return wrapper.get('button[aria-label="配置画布背景"]')
}

function getPanel(): HTMLElement {
  const panel = document.querySelector<HTMLElement>(
    '.step-canvas-background-control'
  )
  if (!panel) {
    throw new Error('背景设置弹层未渲染。')
  }
  return panel
}

function clickRadio(label: string): void {
  const button = [...document.querySelectorAll<HTMLElement>('.el-radio-button')]
    .find((item: HTMLElement): boolean => item.textContent?.trim() === label)
  if (!button) {
    throw new Error(`未找到背景选项：${label}`)
  }
  button.click()
}

afterEach((): void => {
  mountedWrappers.splice(0).forEach((wrapper: VueWrapper): void => {
    wrapper.unmount()
  })
  document.body.replaceChildren()
  vi.restoreAllMocks()
})

describe('StepCanvasBackgroundControl', (): void => {
  it('opens a visible in-component panel and switches all background kinds', async (): Promise<void> => {
    const warningSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const wrapper = mountControl()
    const trigger = getTrigger(wrapper)

    expect(trigger.attributes()).toMatchObject({
      'aria-expanded': 'false',
      'aria-haspopup': 'dialog',
      title: '画布背景'
    })

    await trigger.trigger('click')
    await settlePanel()

    expect(trigger.attributes('aria-expanded')).toBe('true')
    const panel = getPanel()
    const panelStyle = window.getComputedStyle(panel)
    const titleId = panel.getAttribute('aria-labelledby')
    expect(panel.getAttribute('role')).toBe('dialog')
    expect(titleId).toBeTruthy()
    expect(document.getElementById(titleId ?? '')?.textContent?.trim()).toBe(
      '画布背景设置'
    )
    expect(panelStyle.opacity).toBe('1')
    expect(panelStyle.visibility).toBe('visible')
    expect(document.querySelector('.el-popper')).toBeNull()

    clickRadio('纯色')
    clickRadio('图片')
    clickRadio('网格')
    await flushPromises()

    expect(wrapper.emitted('patch')).toEqual([
      [{ kind: 'solid' }],
      [{ kind: 'image' }],
      [{ kind: 'grid' }]
    ])
    expect(
      warningSpy.mock.calls.some(
        (call: unknown[]): boolean =>
          String(call[0]).includes('Runtime directive used on component') ||
          String(call[0]).includes('Vue Flow')
      )
    ).toBe(false)
  })

  it.each([
    ['Enter', 'Enter'],
    ['Space', ' ']
  ])('opens from the %s key', async (code: string, key: string): Promise<void> => {
    const wrapper = mountControl()
    const trigger = getTrigger(wrapper)

    trigger.element.dispatchEvent(
      new KeyboardEvent('keydown', {
        bubbles: true,
        cancelable: true,
        code,
        key
      })
    )
    await settlePanel()

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(getPanel()).toBeTruthy()
  })

  it.each([
    ['Escape', (panel: HTMLElement): void => {
      panel.dispatchEvent(
        new KeyboardEvent('keydown', {
          bubbles: true,
          cancelable: true,
          code: 'Escape',
          key: 'Escape'
        })
      )
    }],
    ['outside pointer', (_panel: HTMLElement): void => {
      document.body.dispatchEvent(
        new MouseEvent('pointerdown', {
          bubbles: true,
          cancelable: true
        })
      )
    }]
  ])(
    'closes from %s and returns focus to the trigger',
    async (
      _source: string,
      close: (panel: HTMLElement) => void
    ): Promise<void> => {
      const wrapper = mountControl()
      const trigger = getTrigger(wrapper)
      await trigger.trigger('click')
      await settlePanel()
      const panel = getPanel()
      expect(document.activeElement).toBe(panel)

      close(panel)
      await settlePanel()

      expect(trigger.attributes('aria-expanded')).toBe('false')
      expect(document.querySelector('.step-canvas-background-control')).toBeNull()
      expect(document.activeElement).toBe(trigger.element)
    }
  )

  it('keeps the image upload input keyboard reachable and emits the selected file', async (): Promise<void> => {
    const wrapper = mountControl(createPreference('image'))
    await getTrigger(wrapper).trigger('click')
    await settlePanel()

    const input = getPanel().querySelector<HTMLInputElement>(
      'input[type="file"]'
    )
    expect(input).not.toBeNull()
    expect(input?.getAttribute('aria-label')).toBe('上传画布背景图片')
    expect(input?.tabIndex).toBe(0)
    expect(input?.disabled).toBe(false)

    const file = new File(['background'], 'canvas.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [file]
    })
    input?.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(wrapper.emitted('select-image')).toEqual([[file]])

  })
})
