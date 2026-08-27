import { defineComponent, h } from 'vue'
import {
  flushPromises,
  mount,
  type VueWrapper
} from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import {
  buildStepCanvasImageKey,
  buildStepCanvasPreferenceKey,
  sanitizeStepCanvasDisplayState,
  useStepCanvasPreferences,
  validateStepCanvasBackgroundFile,
  type StepCanvasImageStorage,
  type StepCanvasPreferenceStorage,
  type StepCanvasStorageScope,
  type UseStepCanvasPreferencesOptions,
  type UseStepCanvasPreferencesResult
} from '@/composables/useStepCanvasPreferences'
import { resolveStepCanvasViewportMode } from '@/composables/useStepCanvasViewport'

class MemoryPreferenceStorage implements StepCanvasPreferenceStorage {
  readonly values = new Map<string, string>()

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }
}

class MemoryImageStorage implements StepCanvasImageStorage {
  readonly values = new Map<string, Blob>()
  readonly reads: string[] = []
  writes = 0

  async get(key: string): Promise<Blob | undefined> {
    this.reads.push(key)
    return this.values.get(key)
  }

  async set(key: string, value: Blob): Promise<void> {
    this.writes += 1
    this.values.set(key, value)
  }

  async delete(key: string): Promise<void> {
    this.values.delete(key)
  }
}

interface PreferenceHarness {
  wrapper: VueWrapper
  preferences: UseStepCanvasPreferencesResult
}

const mountedWrappers: VueWrapper[] = []

function makeScope(testCaseId: number): StepCanvasStorageScope {
  return {
    userId: 7,
    workspaceId: 19,
    testCaseId
  }
}

function mountPreferenceHarness(
  scope: StepCanvasStorageScope,
  options: UseStepCanvasPreferencesOptions
): PreferenceHarness {
  let preferences: UseStepCanvasPreferencesResult | null = null
  const Harness = defineComponent({
    setup() {
      preferences = useStepCanvasPreferences(scope, options)
      return (): ReturnType<typeof h> => h('div')
    }
  })
  const wrapper = mount(Harness)
  mountedWrappers.push(wrapper)
  if (!preferences) {
    throw new Error('Preference harness failed to initialize.')
  }
  return { wrapper, preferences }
}

afterEach((): void => {
  mountedWrappers.splice(0).forEach((wrapper: VueWrapper): void => wrapper.unmount())
})

describe('step canvas viewport modes', (): void => {
  it('uses the approved responsive breakpoints', (): void => {
    expect(resolveStepCanvasViewportMode(1280)).toBe('desktop')
    expect(resolveStepCanvasViewportMode(1279)).toBe('medium')
    expect(resolveStepCanvasViewportMode(960)).toBe('medium')
    expect(resolveStepCanvasViewportMode(959)).toBe('compact')
  })
})

describe('step canvas preference validation', (): void => {
  it('builds isolated keys and rejects unsupported or oversized images', (): void => {
    const firstScope = makeScope(31)
    const secondScope = makeScope(32)

    expect(buildStepCanvasPreferenceKey(firstScope)).not.toBe(
      buildStepCanvasPreferenceKey(secondScope)
    )
    expect(buildStepCanvasImageKey(firstScope)).not.toBe(
      buildStepCanvasImageKey(secondScope)
    )
    expect(
      validateStepCanvasBackgroundFile(
        new File(['image'], 'background.png', { type: 'image/png' })
      )
    ).toBeNull()
    expect(
      validateStepCanvasBackgroundFile(
        new File(['image'], 'background.gif', { type: 'image/gif' })
      )
    ).toContain('PNG、JPEG 或 WebP')
    expect(
      validateStepCanvasBackgroundFile(
        new File(
          [new Uint8Array(5 * 1024 * 1024 + 1)],
          'background.webp',
          { type: 'image/webp' }
        )
      )
    ).toContain('5 MB')
  })

  it('sanitizes malformed local data instead of leaking invalid graph state', (): void => {
    const state = sanitizeStepCanvasDisplayState({
      nodeStates: {
        'top:0': { position: { x: 12, y: 24 }, shape: 'rounded' },
        'not-a-path': { position: { x: 1, y: 2 } }
      },
      annotations: [
        {
          id: 'ok',
          source: 'top:0',
          target: 'top:1',
          kind: 'dependency'
        },
        {
          id: 'bad',
          source: 'root',
          target: 'top:1',
          kind: 'parallel'
        }
      ],
      connectionStyle: 'invalid',
      background: { kind: 'solid', color: '#123456' }
    })

    expect(state.nodeStates).toEqual({
      'top:0': { position: { x: 12, y: 24 }, shape: 'rounded' }
    })
    expect(state.annotations).toHaveLength(1)
    expect(state.connectionStyle).toBe('bezier')
    expect(state.background).toEqual({ kind: 'solid', color: '#123456' })
  })
})

describe('step canvas preference persistence', (): void => {
  it('migrates legacy horizontal coordinates without discarding other preferences', async (): Promise<void> => {
    const preferenceStorage = new MemoryPreferenceStorage()
    const imageStorage = new MemoryImageStorage()
    const scope = makeScope(40)
    const currentKey = buildStepCanvasPreferenceKey(scope)
    const legacyKey = currentKey.replace(
      'vat:step-canvas:preferences:v2',
      'vat:step-canvas:preferences:v1'
    )
    preferenceStorage.setItem(
      legacyKey,
      JSON.stringify({
        nodeStates: {
          'top:0': {
            position: { x: 640, y: 24 },
            collapsed: true,
            color: '#2563eb',
            shape: 'rounded'
          }
        },
        annotations: [],
        connectionStyle: 'step',
        background: { kind: 'solid', color: '#f8fafc' }
      })
    )

    const harness = mountPreferenceHarness(scope, {
      preferenceStorage,
      imageStorage,
      createObjectUrl: (_blob: Blob): string => 'blob:unused',
      revokeObjectUrl: (_url: string): void => undefined,
      persistDelayMs: 0
    })
    await flushPromises()

    expect(harness.preferences.displayState.value.nodeStates['top:0']).toEqual({
      collapsed: true,
      color: '#2563eb',
      shape: 'rounded'
    })
    expect(harness.preferences.displayState.value.connectionStyle).toBe('step')
    expect(harness.preferences.displayState.value.background).toEqual({
      kind: 'solid',
      color: '#f8fafc'
    })
    expect(preferenceStorage.getItem(currentKey)).not.toBeNull()
  })

  it('restores ordinary preferences only inside the same user/workspace/case scope', async (): Promise<void> => {
    const preferenceStorage = new MemoryPreferenceStorage()
    const imageStorage = new MemoryImageStorage()
    const options: UseStepCanvasPreferencesOptions = {
      preferenceStorage,
      imageStorage,
      createObjectUrl: (_blob: Blob): string => 'blob:unused',
      revokeObjectUrl: (_url: string): void => undefined,
      persistDelayMs: 0
    }

    const first = mountPreferenceHarness(makeScope(41), options)
    await flushPromises()
    first.preferences.patchBackground({ kind: 'solid', color: '#e2e8f0' })
    first.preferences.updateNodePosition('top:0', { x: 120, y: 80 })
    first.preferences.persistNow()

    const restored = mountPreferenceHarness(makeScope(41), options)
    await flushPromises()
    expect(restored.preferences.displayState.value.background).toEqual({
      kind: 'solid',
      color: '#e2e8f0'
    })
    expect(restored.preferences.displayState.value.nodeStates['top:0']?.position).toEqual({
      x: 120,
      y: 80
    })

    const isolated = mountPreferenceHarness(makeScope(42), options)
    await flushPromises()
    expect(isolated.preferences.displayState.value.background).toEqual({ kind: 'grid' })
    expect(isolated.preferences.displayState.value.nodeStates).toEqual({})
  })

  it('persists node styles and annotation-only relations locally', async (): Promise<void> => {
    const preferenceStorage = new MemoryPreferenceStorage()
    const imageStorage = new MemoryImageStorage()
    const options: UseStepCanvasPreferencesOptions = {
      preferenceStorage,
      imageStorage,
      createObjectUrl: (_blob: Blob): string => 'blob:unused',
      revokeObjectUrl: (_url: string): void => undefined,
      persistDelayMs: 0
    }
    const scope = makeScope(45)
    const first = mountPreferenceHarness(scope, options)
    await flushPromises()
    first.preferences.replaceDisplayState({
      nodeStates: {
        'top:0': {
          color: '#2563eb',
          shape: 'rounded',
          size: 'large'
        }
      },
      annotations: [
        {
          id: 'parallel-note',
          source: 'top:0',
          target: 'top:1',
          kind: 'parallel',
          label: '准备阶段'
        }
      ],
      connectionStyle: 'step',
      background: { kind: 'grid' }
    })
    first.preferences.persistNow()

    const restored = mountPreferenceHarness(scope, options)
    await flushPromises()
    expect(restored.preferences.displayState.value.nodeStates['top:0']).toEqual({
      color: '#2563eb',
      shape: 'rounded',
      size: 'large'
    })
    expect(restored.preferences.displayState.value.annotations).toEqual([
      expect.objectContaining({
        id: 'parallel-note',
        kind: 'parallel',
        label: '准备阶段'
      })
    ])
  })

  it('stores image bytes in the scoped image store and restores an object URL', async (): Promise<void> => {
    const preferenceStorage = new MemoryPreferenceStorage()
    const imageStorage = new MemoryImageStorage()
    const revokedUrls: string[] = []
    let objectUrlSequence = 0
    const options: UseStepCanvasPreferencesOptions = {
      preferenceStorage,
      imageStorage,
      createObjectUrl: (_blob: Blob): string => `blob:canvas-${++objectUrlSequence}`,
      revokeObjectUrl: (url: string): void => {
        revokedUrls.push(url)
      },
      persistDelayMs: 0
    }
    const scope = makeScope(51)
    const imageKey = buildStepCanvasImageKey(scope)
    const first = mountPreferenceHarness(scope, options)
    await flushPromises()

    await first.preferences.saveBackgroundImage(
      new File(['valid-image'], 'background.jpg', { type: 'image/jpeg' })
    )
    expect(imageStorage.values.get(imageKey)).toBeInstanceOf(Blob)
    expect(first.preferences.displayState.value.background).toMatchObject({
      kind: 'image',
      imageKey,
      imageFit: 'cover'
    })
    expect(first.preferences.backgroundImageUrl.value).toBe('blob:canvas-1')
    expect(imageStorage.writes).toBe(1)

    await expect(
      first.preferences.saveBackgroundImage(
        new File(['invalid'], 'background.svg', { type: 'image/svg+xml' })
      )
    ).rejects.toThrow('PNG、JPEG 或 WebP')
    expect(imageStorage.writes).toBe(1)

    first.preferences.persistNow()
    first.wrapper.unmount()
    const restored = mountPreferenceHarness(scope, options)
    await flushPromises()

    expect(imageStorage.reads).toContain(imageKey)
    expect(restored.preferences.backgroundImageUrl.value).toBe('blob:canvas-2')
    expect(revokedUrls).toContain('blob:canvas-1')
  })
})
