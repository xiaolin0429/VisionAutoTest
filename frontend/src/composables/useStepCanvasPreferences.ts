import {
  computed,
  onBeforeUnmount,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref
} from 'vue'
import { useDebounceFn } from '@vueuse/core'

import type {
  StepGraphAnnotation,
  StepGraphBackgroundPreference,
  StepGraphDisplayState,
  StepGraphNodeDisplayState,
  StepGraphPosition,
  StepStructurePath
} from '@/types/stepGraph'
import {
  createDefaultStepGraphDisplayState,
  isEditableStepPath,
  parseStepStructurePath
} from '@/utils/stepGraph'

export interface StepCanvasStorageScope {
  userId: number
  workspaceId: number
  testCaseId: number
}

export interface StepCanvasPreferenceStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface StepCanvasImageStorage {
  get(key: string): Promise<Blob | undefined>
  set(key: string, value: Blob): Promise<void>
  delete(key: string): Promise<void>
}

export type StepCanvasBackgroundPatch = Omit<
  Partial<StepGraphBackgroundPreference>,
  'imageKey'
>

export interface UseStepCanvasPreferencesOptions {
  preferenceStorage?: StepCanvasPreferenceStorage
  imageStorage?: StepCanvasImageStorage
  createObjectUrl?: (blob: Blob) => string
  revokeObjectUrl?: (url: string) => void
  persistDelayMs?: number
}

export interface UseStepCanvasPreferencesResult {
  displayState: Ref<StepGraphDisplayState>
  backgroundImageUrl: Ref<string | null>
  loaded: Ref<boolean>
  preferenceError: Ref<string>
  load: () => Promise<void>
  persistNow: () => void
  replaceDisplayState: (nextState: StepGraphDisplayState) => void
  patchBackground: (patch: StepCanvasBackgroundPatch) => void
  updateNodePosition: (path: StepStructurePath, position: StepGraphPosition) => void
  saveBackgroundImage: (file: File) => Promise<void>
  clearBackgroundImage: () => Promise<void>
}

const PREFERENCE_KEY_PREFIX = 'vat:step-canvas:preferences:v2'
const LEGACY_PREFERENCE_KEY_PREFIX = 'vat:step-canvas:preferences:v1'
const IMAGE_KEY_PREFIX = 'vat:step-canvas:background:v1'
const IMAGE_DATABASE_NAME = 'visionautotest-step-canvas'
const IMAGE_DATABASE_VERSION = 1
const IMAGE_STORE_NAME = 'background-images'
const MAX_BACKGROUND_IMAGE_BYTES = 5 * 1024 * 1024
const SUPPORTED_BACKGROUND_IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp'
])

let imageDatabasePromise: Promise<IDBDatabase> | null = null

function encodeScopePart(value: number): string {
  return encodeURIComponent(String(value))
}

export function buildStepCanvasPreferenceKey(scope: StepCanvasStorageScope): string {
  return buildScopedPreferenceKey(PREFERENCE_KEY_PREFIX, scope)
}

function buildLegacyStepCanvasPreferenceKey(scope: StepCanvasStorageScope): string {
  return buildScopedPreferenceKey(LEGACY_PREFERENCE_KEY_PREFIX, scope)
}

function buildScopedPreferenceKey(
  prefix: string,
  scope: StepCanvasStorageScope
): string {
  return [
    prefix,
    `user:${encodeScopePart(scope.userId)}`,
    `workspace:${encodeScopePart(scope.workspaceId)}`,
    `case:${encodeScopePart(scope.testCaseId)}`
  ].join(':')
}

export function buildStepCanvasImageKey(scope: StepCanvasStorageScope): string {
  return [
    IMAGE_KEY_PREFIX,
    `user:${encodeScopePart(scope.userId)}`,
    `workspace:${encodeScopePart(scope.workspaceId)}`,
    `case:${encodeScopePart(scope.testCaseId)}`
  ].join(':')
}

export function validateStepCanvasBackgroundFile(file: File): string | null {
  if (!SUPPORTED_BACKGROUND_IMAGE_TYPES.has(file.type)) {
    return '背景图片仅支持 PNG、JPEG 或 WebP 格式。'
  }
  if (file.size > MAX_BACKGROUND_IMAGE_BYTES) {
    return '背景图片不能超过 5 MB。'
  }
  return null
}

function cloneValue<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item: unknown): unknown => cloneValue(item)) as T
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(
        ([key, item]: [string, unknown]): [string, unknown] => [key, cloneValue(item)]
      )
    ) as T
  }
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isFinitePosition(value: unknown): value is StepGraphPosition {
  return (
    isRecord(value) &&
    typeof value.x === 'number' &&
    Number.isFinite(value.x) &&
    typeof value.y === 'number' &&
    Number.isFinite(value.y)
  )
}

function sanitizeNodeState(value: unknown): StepGraphNodeDisplayState | null {
  if (!isRecord(value)) {
    return null
  }

  const state: StepGraphNodeDisplayState = {}
  if (isFinitePosition(value.position)) {
    state.position = { x: value.position.x, y: value.position.y }
  }
  if (typeof value.collapsed === 'boolean') {
    state.collapsed = value.collapsed
  }
  if (typeof value.color === 'string' && value.color.trim()) {
    state.color = value.color
  }
  if (value.shape === 'rectangle' || value.shape === 'rounded') {
    state.shape = value.shape
  }
  if (value.size === 'small' || value.size === 'medium' || value.size === 'large') {
    state.size = value.size
  }
  return state
}

function sanitizeAnnotations(value: unknown): StepGraphAnnotation[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((item: unknown): StepGraphAnnotation[] => {
    if (
      !isRecord(item) ||
      typeof item.id !== 'string' ||
      typeof item.source !== 'string' ||
      typeof item.target !== 'string' ||
      !isEditableStepPath(item.source) ||
      !isEditableStepPath(item.target) ||
      (item.kind !== 'dependency' && item.kind !== 'parallel')
    ) {
      return []
    }

    return [
      {
        id: item.id,
        source: item.source,
        target: item.target,
        kind: item.kind,
        ...(typeof item.label === 'string' ? { label: item.label } : {})
      }
    ]
  })
}

function sanitizeBackground(value: unknown): StepGraphBackgroundPreference {
  const fallback = createDefaultStepGraphDisplayState().background
  if (!isRecord(value)) {
    return fallback
  }

  const kind =
    value.kind === 'solid' || value.kind === 'image' || value.kind === 'grid'
      ? value.kind
      : fallback.kind
  const imageOpacity =
    typeof value.imageOpacity === 'number' && Number.isFinite(value.imageOpacity)
      ? Math.min(Math.max(value.imageOpacity, 0.1), 1)
      : undefined
  const imageFit =
    value.imageFit === 'cover' || value.imageFit === 'contain' || value.imageFit === 'repeat'
      ? value.imageFit
      : undefined

  return {
    kind,
    ...(typeof value.color === 'string' && value.color.trim()
      ? { color: value.color }
      : {}),
    ...(typeof value.imageKey === 'string' && value.imageKey.trim()
      ? { imageKey: value.imageKey }
      : {}),
    ...(imageOpacity === undefined ? {} : { imageOpacity }),
    ...(imageFit === undefined ? {} : { imageFit }),
    ...(typeof value.imageFixed === 'boolean' ? { imageFixed: value.imageFixed } : {})
  }
}

export function sanitizeStepCanvasDisplayState(value: unknown): StepGraphDisplayState {
  const fallback = createDefaultStepGraphDisplayState()
  if (!isRecord(value)) {
    return fallback
  }

  const nodeStates: Record<string, StepGraphNodeDisplayState> = {}
  if (isRecord(value.nodeStates)) {
    for (const [path, rawState] of Object.entries(value.nodeStates)) {
      if (!parseStepStructurePath(path)) {
        continue
      }
      const state = sanitizeNodeState(rawState)
      if (state) {
        nodeStates[path] = state
      }
    }
  }

  return {
    nodeStates,
    annotations: sanitizeAnnotations(value.annotations),
    connectionStyle:
      value.connectionStyle === 'straight' ||
      value.connectionStyle === 'step' ||
      value.connectionStyle === 'bezier'
        ? value.connectionStyle
        : fallback.connectionStyle,
    background: sanitizeBackground(value.background)
  }
}

function removeLegacyNodePositions(
  state: StepGraphDisplayState
): StepGraphDisplayState {
  return {
    ...state,
    nodeStates: Object.fromEntries(
      Object.entries(state.nodeStates).map(
        ([path, nodeState]: [string, StepGraphNodeDisplayState]): [
          string,
          StepGraphNodeDisplayState
        ] => {
          const { position: _position, ...remainingState } = nodeState
          return [path, remainingState]
        }
      )
    )
  }
}

function defaultPreferenceStorage(): StepCanvasPreferenceStorage {
  return {
    getItem(key: string): string | null {
      return window.localStorage.getItem(key)
    },
    setItem(key: string, value: string): void {
      window.localStorage.setItem(key, value)
    },
    removeItem(key: string): void {
      window.localStorage.removeItem(key)
    }
  }
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise<T>((resolve: (value: T) => void, reject: (reason?: unknown) => void) => {
    request.onsuccess = (): void => resolve(request.result)
    request.onerror = (): void =>
      reject(request.error ?? new Error('IndexedDB request failed.'))
  })
}

function transactionCompletion(transaction: IDBTransaction): Promise<void> {
  return new Promise<void>(
    (resolve: () => void, reject: (reason?: unknown) => void): void => {
      transaction.oncomplete = (): void => resolve()
      transaction.onerror = (): void =>
        reject(transaction.error ?? new Error('IndexedDB transaction failed.'))
      transaction.onabort = (): void =>
        reject(transaction.error ?? new Error('IndexedDB transaction was aborted.'))
    }
  )
}

function openImageDatabase(): Promise<IDBDatabase> {
  if (imageDatabasePromise) {
    return imageDatabasePromise
  }

  imageDatabasePromise = new Promise<IDBDatabase>(
    (
      resolve: (database: IDBDatabase) => void,
      reject: (reason?: unknown) => void
    ): void => {
      if (typeof indexedDB === 'undefined') {
        reject(new Error('IndexedDB is unavailable.'))
        return
      }

      const request = indexedDB.open(IMAGE_DATABASE_NAME, IMAGE_DATABASE_VERSION)
      request.onupgradeneeded = (): void => {
        const database = request.result
        if (!database.objectStoreNames.contains(IMAGE_STORE_NAME)) {
          database.createObjectStore(IMAGE_STORE_NAME)
        }
      }
      request.onsuccess = (): void => resolve(request.result)
      request.onerror = (): void =>
        reject(request.error ?? new Error('Unable to open the canvas image database.'))
      request.onblocked = (): void =>
        reject(new Error('Canvas image database upgrade is blocked.'))
    }
  ).catch((error: unknown): never => {
    imageDatabasePromise = null
    throw error
  })

  return imageDatabasePromise
}

export function createIndexedDbStepCanvasImageStorage(): StepCanvasImageStorage {
  return {
    async get(key: string): Promise<Blob | undefined> {
      const database = await openImageDatabase()
      const transaction = database.transaction(IMAGE_STORE_NAME, 'readonly')
      const request = transaction.objectStore(IMAGE_STORE_NAME).get(key)
      return requestResult(request) as Promise<Blob | undefined>
    },
    async set(key: string, value: Blob): Promise<void> {
      const database = await openImageDatabase()
      const transaction = database.transaction(IMAGE_STORE_NAME, 'readwrite')
      const completion = transactionCompletion(transaction)
      transaction.objectStore(IMAGE_STORE_NAME).put(value, key)
      await completion
    },
    async delete(key: string): Promise<void> {
      const database = await openImageDatabase()
      const transaction = database.transaction(IMAGE_STORE_NAME, 'readwrite')
      const completion = transactionCompletion(transaction)
      transaction.objectStore(IMAGE_STORE_NAME).delete(key)
      await completion
    }
  }
}

export function useStepCanvasPreferences(
  scope: MaybeRefOrGetter<StepCanvasStorageScope>,
  options: UseStepCanvasPreferencesOptions = {}
): UseStepCanvasPreferencesResult {
  const preferenceStorage = options.preferenceStorage ?? defaultPreferenceStorage()
  const imageStorage =
    options.imageStorage ?? createIndexedDbStepCanvasImageStorage()
  const createObjectUrl =
    options.createObjectUrl ?? ((blob: Blob): string => URL.createObjectURL(blob))
  const revokeObjectUrl =
    options.revokeObjectUrl ?? ((url: string): void => URL.revokeObjectURL(url))
  const scopeValue = computed((): StepCanvasStorageScope => toValue(scope))
  const preferenceKey = computed((): string =>
    buildStepCanvasPreferenceKey(scopeValue.value)
  )
  const imageKey = computed((): string => buildStepCanvasImageKey(scopeValue.value))

  const displayState = ref<StepGraphDisplayState>(
    createDefaultStepGraphDisplayState()
  )
  const backgroundImageUrl = ref<string | null>(null)
  const loaded = ref(false)
  const preferenceError = ref('')
  let loadSequence = 0

  function replaceObjectUrl(nextUrl: string | null): void {
    if (backgroundImageUrl.value) {
      revokeObjectUrl(backgroundImageUrl.value)
    }
    backgroundImageUrl.value = nextUrl
  }

  function writePreferences(key: string, state: StepGraphDisplayState): void {
    try {
      preferenceStorage.setItem(key, JSON.stringify(state))
    } catch {
      preferenceError.value = '画布偏好无法写入浏览器本地存储。'
    }
  }

  const persistDebounced = useDebounceFn(
    (key: string, state: StepGraphDisplayState): void => {
      writePreferences(key, state)
    },
    options.persistDelayMs ?? 250
  )

  async function load(): Promise<void> {
    const sequence = ++loadSequence
    const activePreferenceKey = preferenceKey.value
    const activeImageKey = imageKey.value
    loaded.value = false
    preferenceError.value = ''
    replaceObjectUrl(null)

    let nextState = createDefaultStepGraphDisplayState()
    let migratedLegacyPreferences = false
    try {
      const storedValue = preferenceStorage.getItem(activePreferenceKey)
      if (storedValue) {
        nextState = sanitizeStepCanvasDisplayState(JSON.parse(storedValue) as unknown)
      } else {
        const legacyKey = buildLegacyStepCanvasPreferenceKey(scopeValue.value)
        const legacyValue = preferenceStorage.getItem(legacyKey)
        if (legacyValue) {
          nextState = removeLegacyNodePositions(
            sanitizeStepCanvasDisplayState(JSON.parse(legacyValue) as unknown)
          )
          migratedLegacyPreferences = true
        }
      }
    } catch {
      preferenceError.value = '画布偏好已损坏，已恢复默认设置。'
    }

    if (
      nextState.background.kind === 'image' &&
      nextState.background.imageKey &&
      nextState.background.imageKey !== activeImageKey
    ) {
      nextState.background = { kind: 'grid' }
      preferenceError.value = '背景图片作用域不匹配，已恢复默认网格。'
    }

    if (
      nextState.background.kind === 'image' &&
      nextState.background.imageKey === activeImageKey
    ) {
      try {
        const blob = await imageStorage.get(activeImageKey)
        if (blob && sequence === loadSequence) {
          replaceObjectUrl(createObjectUrl(blob))
        } else if (!blob) {
          preferenceError.value = '未找到已保存的背景图片，请重新上传。'
        }
      } catch {
        preferenceError.value = '背景图片无法从浏览器本地数据库恢复。'
      }
    }

    if (sequence !== loadSequence) {
      return
    }
    displayState.value = nextState
    loaded.value = true
    if (migratedLegacyPreferences) {
      writePreferences(activePreferenceKey, nextState)
    }
  }

  function persistNow(): void {
    if (!loaded.value) {
      return
    }
    writePreferences(preferenceKey.value, displayState.value)
  }

  function replaceDisplayState(nextState: StepGraphDisplayState): void {
    displayState.value = sanitizeStepCanvasDisplayState(nextState)
  }

  function patchBackground(patch: StepCanvasBackgroundPatch): void {
    displayState.value = {
      ...displayState.value,
      background: {
        ...displayState.value.background,
        ...patch
      }
    }
  }

  function updateNodePosition(
    path: StepStructurePath,
    position: StepGraphPosition
  ): void {
    if (!Number.isFinite(position.x) || !Number.isFinite(position.y)) {
      return
    }
    const currentNodeState = displayState.value.nodeStates[path] ?? {}
    displayState.value = {
      ...displayState.value,
      nodeStates: {
        ...displayState.value.nodeStates,
        [path]: {
          ...currentNodeState,
          position: { x: position.x, y: position.y }
        }
      }
    }
  }

  async function saveBackgroundImage(file: File): Promise<void> {
    const validationError = validateStepCanvasBackgroundFile(file)
    if (validationError) {
      throw new Error(validationError)
    }

    const activeImageKey = imageKey.value
    try {
      await imageStorage.set(activeImageKey, file)
      replaceObjectUrl(createObjectUrl(file))
      displayState.value = {
        ...displayState.value,
        background: {
          ...displayState.value.background,
          kind: 'image',
          imageKey: activeImageKey,
          imageOpacity: displayState.value.background.imageOpacity ?? 0.65,
          imageFit: displayState.value.background.imageFit ?? 'cover',
          imageFixed: displayState.value.background.imageFixed ?? true
        }
      }
      preferenceError.value = ''
      persistNow()
    } catch (error: unknown) {
      if (error instanceof Error && error.message !== validationError) {
        throw new Error('背景图片无法写入浏览器本地数据库。')
      }
      throw error
    }
  }

  async function clearBackgroundImage(): Promise<void> {
    const activeImageKey = imageKey.value
    try {
      await imageStorage.delete(activeImageKey)
    } finally {
      replaceObjectUrl(null)
      displayState.value = {
        ...displayState.value,
        background: { kind: 'grid' }
      }
      persistNow()
    }
  }

  watch(
    displayState,
    (nextState: StepGraphDisplayState): void => {
      if (!loaded.value) {
        return
      }
      void persistDebounced(preferenceKey.value, cloneValue(nextState))
    },
    { deep: true }
  )

  watch(
    preferenceKey,
    (_nextKey: string, _previousKey: string | undefined): void => {
      void load()
    },
    { immediate: true }
  )

  onBeforeUnmount((): void => {
    persistNow()
    replaceObjectUrl(null)
  })

  return {
    displayState,
    backgroundImageUrl,
    loaded,
    preferenceError,
    load,
    persistNow,
    replaceDisplayState,
    patchBackground,
    updateNodePosition,
    saveBackgroundImage,
    clearBackgroundImage
  }
}
