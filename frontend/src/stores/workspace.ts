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

  function setWorkspaces(items: Workspace[]) {
    workspaces.value = items
    if (!items.some((item) => item.id === currentWorkspaceId.value)) {
      currentWorkspaceId.value = items[0]?.id ?? null
    }
  }

  function setCurrentWorkspace(id: number) {
    currentWorkspaceId.value = id
  }

  async function bootstrap() {
    const items = await listWorkspaces()
    setWorkspaces(items)
  }

  function reset() {
    workspaces.value = []
    currentWorkspaceId.value = null
  }

  return {
    workspaces,
    currentWorkspaceId,
    currentWorkspace,
    setWorkspaces,
    setCurrentWorkspace,
    bootstrap,
    reset
  }
})
