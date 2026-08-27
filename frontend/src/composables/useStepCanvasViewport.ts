import { computed, type ComputedRef } from 'vue'
import { useWindowSize } from '@vueuse/core'

export type StepCanvasViewportMode = 'desktop' | 'medium' | 'compact'

export function resolveStepCanvasViewportMode(width: number): StepCanvasViewportMode {
  if (width >= 1280) {
    return 'desktop'
  }
  if (width >= 960) {
    return 'medium'
  }
  return 'compact'
}

export function useStepCanvasViewportMode(): ComputedRef<StepCanvasViewportMode> {
  const { width } = useWindowSize({ initialWidth: 1440 })
  return computed((): StepCanvasViewportMode =>
    resolveStepCanvasViewportMode(width.value)
  )
}
