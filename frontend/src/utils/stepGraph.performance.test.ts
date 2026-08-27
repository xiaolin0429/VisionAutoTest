import { describe, expect, it } from 'vitest'

import { createLargeStepCanvasFixture } from '@/dev/stepCanvasFixtures'
import type { StepGraph, StepGraphNode } from '@/types/stepGraph'
import {
  layoutStepGraph,
  projectStepDraftsToGraph,
  reorderStepDrafts
} from '@/utils/stepGraph'

interface PerformanceMeasurement {
  medianMs: number
  p95Ms: number
  maxMs: number
  samples: number
}

function percentile(samples: readonly number[], fraction: number): number {
  const ordered = [...samples].sort((left: number, right: number): number => left - right)
  const index = Math.min(
    ordered.length - 1,
    Math.max(0, Math.ceil(ordered.length * fraction) - 1)
  )
  return ordered[index]
}

function measureRepeatedly(
  operation: () => unknown,
  options: {
    warmups: number
    samples: number
  }
): PerformanceMeasurement {
  for (let index = 0; index < options.warmups; index += 1) {
    operation()
  }

  const durations: number[] = []
  for (let index = 0; index < options.samples; index += 1) {
    const startedAt = performance.now()
    operation()
    durations.push(performance.now() - startedAt)
  }

  return {
    medianMs: percentile(durations, 0.5),
    p95Ms: percentile(durations, 0.95),
    maxMs: Math.max(...durations),
    samples: durations.length
  }
}

function roundMeasurement(
  measurement: PerformanceMeasurement
): PerformanceMeasurement {
  return {
    medianMs: Number(measurement.medianMs.toFixed(2)),
    p95Ms: Number(measurement.p95Ms.toFixed(2)),
    maxMs: Number(measurement.maxMs.toFixed(2)),
    samples: measurement.samples
  }
}

describe('150-step canvas performance', (): void => {
  it('repeatedly measures projection, Dagre layout, and structural command feedback', (): void => {
    const fixture = createLargeStepCanvasFixture()
    const project = (): StepGraph =>
      projectStepDraftsToGraph(fixture.drafts, {
        annotations: fixture.annotations
      })
    const projected = project()

    expect(
      projected.nodes.filter((node: StepGraphNode): boolean => node.editable)
    ).toHaveLength(fixture.editableNodeCount)
    expect(projected.nodes).toHaveLength(fixture.editableNodeCount + 1)
    expect(projected.edges).toHaveLength(fixture.edgeCount)

    const projection = measureRepeatedly(project, {
      warmups: 5,
      samples: 30
    })
    const dagreLayout = measureRepeatedly(
      (): StepGraph => layoutStepGraph(projected),
      {
        warmups: 3,
        samples: 20
      }
    )
    const firstInteractiveEnginePath = measureRepeatedly(
      (): StepGraph => layoutStepGraph(project()),
      {
        warmups: 3,
        samples: 15
      }
    )
    const structureCommand = measureRepeatedly(
      () => reorderStepDrafts(
        fixture.drafts,
        'root',
        fixture.drafts.length - 1,
        0
      ),
      {
        warmups: 5,
        samples: 30
      }
    )

    const report = {
      fixture: {
        editableNodes: fixture.editableNodeCount,
        projectedNodes: projected.nodes.length,
        edges: projected.edges.length
      },
      projection: roundMeasurement(projection),
      dagreLayout: roundMeasurement(dagreLayout),
      firstInteractiveEnginePath: roundMeasurement(firstInteractiveEnginePath),
      structureCommand: roundMeasurement(structureCommand)
    }
    console.info(`[step-canvas-performance] ${JSON.stringify(report)}`)

    // These are product budgets, not micro-benchmark guesses. Warmups and P95
    // sampling make regressions reproducible without asserting sub-millisecond noise.
    expect(firstInteractiveEnginePath.p95Ms).toBeLessThan(1_500)
    expect(dagreLayout.p95Ms).toBeLessThan(300)
    expect(structureCommand.p95Ms).toBeLessThan(100)
  })
})
