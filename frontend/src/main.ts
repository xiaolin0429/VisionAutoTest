import { createApp } from 'vue'
import App from './App.vue'
import { installElementPlus } from './plugins/element'
import router from './router'
import { reportAppError } from './utils/error'
import { pinia } from './stores/pinia'
import './styles/index.css'

const app = createApp(App)

app.config.errorHandler = (error) => {
  console.error('[vue-error]', error)
  void reportAppError(router, error, 'vue')
}

window.addEventListener('error', (event) => {
  console.error('[window-error]', event.error ?? event.message)
  void reportAppError(router, event.error ?? event.message, 'window')
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('[unhandled-rejection]', event.reason)
  void reportAppError(router, event.reason, 'promise')
})

router.onError((error) => {
  console.error('[router-error]', error)
  void reportAppError(router, error, 'router')
})

app.use(pinia)
app.use(router)
installElementPlus(app)
app.mount('#app')
