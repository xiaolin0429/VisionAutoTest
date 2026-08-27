export type StepCanvasShortcutCommand =
  | 'save'
  | 'undo'
  | 'redo'
  | 'copy'
  | 'cut'
  | 'paste'
  | 'duplicate'
  | 'delete'
  | 'fit-view'
  | 'reset-zoom'
  | 'auto-layout'
  | 'create-step'
  | 'open-inspector'
  | 'close'
  | 'reorder-previous'
  | 'reorder-next'
  | 'navigate-left'
  | 'navigate-right'
  | 'navigate-up'
  | 'navigate-down'

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false
  }
  return Boolean(
    target.closest(
      [
        'input',
        'textarea',
        'select',
        '[contenteditable]:not([contenteditable="false"])',
        '[role="textbox"]',
        '[role="combobox"]',
        '[role="spinbutton"]'
      ].join(', ')
    )
  )
}

function isNonCanvasInteractiveTarget(target: EventTarget | null): boolean {
  if (
    !(target instanceof Element) ||
    target.matches('.step-execution-node')
  ) {
    return false
  }
  return Boolean(
    target.closest(
      [
        'button',
        'a[href]',
        '[role="button"]',
        '[role="menuitem"]',
        '[role="radio"]',
        '[role="slider"]',
        '[role="tab"]'
      ].join(', ')
    )
  )
}

export function isStepCanvasShortcutBlocked(event: KeyboardEvent): boolean {
  return (
    event.defaultPrevented ||
    event.isComposing ||
    event.keyCode === 229 ||
    isEditableTarget(event.target) ||
    isNonCanvasInteractiveTarget(event.target)
  )
}

export function resolveStepCanvasShortcut(
  event: KeyboardEvent
): StepCanvasShortcutCommand | null {
  if (isStepCanvasShortcutBlocked(event)) {
    return null
  }

  const key = event.key.toLowerCase()
  const modifier = event.metaKey || event.ctrlKey
  if (modifier) {
    if (key === 's') return 'save'
    if (key === 'z') return event.shiftKey ? 'redo' : 'undo'
    if (key === 'y') return 'redo'
    if (key === 'c') return 'copy'
    if (key === 'x') return 'cut'
    if (key === 'v') return 'paste'
    if (key === 'd') return 'duplicate'
    return null
  }

  if (event.altKey && !event.shiftKey) {
    if (key === 'arrowleft' || key === 'arrowup') return 'reorder-previous'
    if (key === 'arrowright' || key === 'arrowdown') return 'reorder-next'
    return null
  }

  if (event.shiftKey) {
    return null
  }
  if (key === 'n') return 'create-step'
  if (key === 'enter') return 'open-inspector'
  if (key === 'escape') return 'close'
  if (key === 'delete' || key === 'backspace') return 'delete'
  if (key === 'f') return 'fit-view'
  if (key === '0') return 'reset-zoom'
  if (key === 'l') return 'auto-layout'
  if (key === 'arrowleft') return 'navigate-left'
  if (key === 'arrowright') return 'navigate-right'
  if (key === 'arrowup') return 'navigate-up'
  if (key === 'arrowdown') return 'navigate-down'
  return null
}
