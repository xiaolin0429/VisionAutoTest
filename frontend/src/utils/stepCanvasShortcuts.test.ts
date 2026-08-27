import { afterEach, describe, expect, it } from 'vitest'

import {
  isStepCanvasShortcutBlocked,
  resolveStepCanvasShortcut
} from '@/utils/stepCanvasShortcuts'

function keyboardEvent(
  key: string,
  options: KeyboardEventInit = {},
  target?: Element
): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { key, ...options })
  if (target) {
    Object.defineProperty(event, 'target', { value: target })
  }
  return event
}

afterEach((): void => {
  document.body.replaceChildren()
})

describe('step canvas shortcuts', (): void => {
  it('maps macOS and Windows command variants', (): void => {
    expect(resolveStepCanvasShortcut(keyboardEvent('s', { metaKey: true }))).toBe('save')
    expect(resolveStepCanvasShortcut(keyboardEvent('z', { ctrlKey: true }))).toBe('undo')
    expect(
      resolveStepCanvasShortcut(
        keyboardEvent('z', { ctrlKey: true, shiftKey: true })
      )
    ).toBe('redo')
    expect(resolveStepCanvasShortcut(keyboardEvent('y', { ctrlKey: true }))).toBe('redo')
    expect(resolveStepCanvasShortcut(keyboardEvent('d', { metaKey: true }))).toBe('duplicate')
    expect(resolveStepCanvasShortcut(keyboardEvent('Backspace'))).toBe('delete')
    expect(resolveStepCanvasShortcut(keyboardEvent('ArrowRight'))).toBe('navigate-right')
    expect(resolveStepCanvasShortcut(keyboardEvent('n'))).toBe('create-step')
    expect(resolveStepCanvasShortcut(keyboardEvent('Enter'))).toBe('open-inspector')
    expect(resolveStepCanvasShortcut(keyboardEvent('Escape'))).toBe('close')
    expect(
      resolveStepCanvasShortcut(keyboardEvent('ArrowUp', { altKey: true }))
    ).toBe('reorder-previous')
    expect(
      resolveStepCanvasShortcut(keyboardEvent('ArrowDown', { altKey: true }))
    ).toBe('reorder-next')
  })

  it('blocks editing and non-canvas interactive controls plus IME events', (): void => {
    const input = document.createElement('input')
    const textarea = document.createElement('textarea')
    const select = document.createElement('select')
    const button = document.createElement('button')
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    const textbox = document.createElement('div')
    textbox.setAttribute('role', 'textbox')
    const combobox = document.createElement('div')
    combobox.setAttribute('role', 'combobox')
    const spinbutton = document.createElement('div')
    spinbutton.setAttribute('role', 'spinbutton')
    const tab = document.createElement('div')
    tab.setAttribute('role', 'tab')
    document.body.append(
      input,
      textarea,
      select,
      button,
      editable,
      textbox,
      combobox,
      spinbutton,
      tab
    )

    for (const target of [
      input,
      textarea,
      select,
      button,
      editable,
      textbox,
      combobox,
      spinbutton,
      tab
    ]) {
      const event = keyboardEvent('z', { metaKey: true }, target)
      expect(isStepCanvasShortcutBlocked(event)).toBe(true)
      expect(resolveStepCanvasShortcut(event)).toBeNull()
    }

    const composing = keyboardEvent('z', {
      metaKey: true,
      isComposing: true
    })
    expect(isStepCanvasShortcutBlocked(composing)).toBe(true)
    expect(resolveStepCanvasShortcut(composing)).toBeNull()
  })

  it('keeps directional navigation active on the semantic canvas node', (): void => {
    const node = document.createElement('div')
    node.className = 'step-execution-node'
    node.setAttribute('role', 'button')
    node.tabIndex = 0
    document.body.append(node)

    const event = keyboardEvent('ArrowRight', {}, node)
    expect(isStepCanvasShortcutBlocked(event)).toBe(false)
    expect(resolveStepCanvasShortcut(event)).toBe('navigate-right')
  })
})
