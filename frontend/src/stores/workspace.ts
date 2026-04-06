import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { StorageSerializers, useStorage } from '@vueuse/core'
import { listWorkspaces } from '@/api/modules/workspaces'
import { WORKSPACE_STORAGE_KEY } from '@/constants/storage'
import type { Workspace } from '@/types/models'

export const useWorkspaceStore = defineStore('workspace', () => {
  const workspaces = ref<Workspace[]>([])
  const currentWorkspaceId = useStorage<number | null>(
    WORKSPACE_STORAGE_KEY,
    null,
    undefined,
    {
      serializer: StorageSerializers.number
    }
  )

  const currentWorkspace = computed(() => {
    return workspaces.value.find((item) => item.id === currentWorkspaceId.value) ?? null
  })
  const hasWorkspace = computed(() => workspaces.value.length > 0 && currentWorkspace.value !== null)

  function setWorkspaces(items: Workspace[]) {
    // @param items Latest workspace list visible to the current user.
    // When the persisted workspace id is no longer valid, fall back to the first accessible workspace.
    workspaces.value = items
    if (!items.some((item) => item.id === currentWorkspaceId.value)) {
      currentWorkspaceId.value = items[0]?.id ?? null
    }
  }

  function setCurrentWorkspace(id: number) {
    // @param id Workspace id selected by the user for subsequent API requests.
    currentWorkspaceId.value = id
  }

  async function bootstrap() {
    // @returns Resolves after the store has loaded and normalized the current workspace selection.
    const items = await listWorkspaces()
    setWorkspaces(items)
  }

  function reset() {
    // Clears workspace state when auth/session context is lost.
    workspaces.value = []
    currentWorkspaceId.value = null
  }

  return {
    workspaces,
    currentWorkspaceId,
    currentWorkspace,
    hasWorkspace,
    setWorkspaces,
    setCurrentWorkspace,
    bootstrap,
    reset
  }
})
