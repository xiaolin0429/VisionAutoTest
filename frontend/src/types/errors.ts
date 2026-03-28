export interface AppErrorPayload {
  id: string
  title: string
  message: string
  detail?: string
  source: 'vue' | 'router' | 'window' | 'promise' | 'unknown'
  timestamp: string
}
