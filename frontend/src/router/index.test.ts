import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('development routes', (): void => {
  it('registers the local step canvas preview in the development test environment', (): void => {
    expect(import.meta.env.DEV).toBe(true)
    expect(router.hasRoute('dev-step-canvas')).toBe(true)
    expect(router.resolve('/__dev/step-canvas')).toMatchObject({
      name: 'dev-step-canvas',
      path: '/__dev/step-canvas',
      meta: expect.objectContaining({
        public: true,
        requiresWorkspace: false
      })
    })
  })

  it('resolves component preview navigation with the target component query', (): void => {
    expect(
      router.resolve({
        name: 'components',
        query: { componentId: '42' }
      })
    ).toMatchObject({
      name: 'components',
      path: '/components',
      fullPath: '/components?componentId=42',
      query: { componentId: '42' }
    })
  })
})
