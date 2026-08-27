export const STEP_CANVAS_BODY_CLASS = 'step-canvas-open'

const activeOwners = new Set<symbol>()

export function setStepCanvasBodyMode(owner: symbol, active: boolean): void {
  if (active) {
    activeOwners.add(owner)
  } else {
    activeOwners.delete(owner)
  }

  if (typeof document !== 'undefined') {
    document.body.classList.toggle(
      STEP_CANVAS_BODY_CLASS,
      activeOwners.size > 0
    )
  }
}
