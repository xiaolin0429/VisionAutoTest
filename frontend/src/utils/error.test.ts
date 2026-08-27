import { describe, expect, it } from 'vitest'

import { isBenignResizeObserverErrorEvent } from './error'

function createErrorEvent(message: string, error: unknown = null): ErrorEvent {
  return new ErrorEvent('error', {
    message,
    error
  })
}

describe('isBenignResizeObserverErrorEvent', (): void => {
  it.each([
    'ResizeObserver loop limit exceeded',
    'ResizeObserver loop completed with undelivered notifications.'
  ])('recognizes the browser ResizeObserver diagnostic: %s', (message: string): void => {
    expect(isBenignResizeObserverErrorEvent(createErrorEvent(message))).toBe(true)
  })

  it('does not hide an actual Error with the same message', (): void => {
    const message = 'ResizeObserver loop completed with undelivered notifications.'

    expect(
      isBenignResizeObserverErrorEvent(
        createErrorEvent(message, new Error(message))
      )
    ).toBe(false)
  })

  it('does not hide unrelated or near-matching window errors', (): void => {
    expect(
      isBenignResizeObserverErrorEvent(createErrorEvent('ResizeObserver failed'))
    ).toBe(false)
    expect(
      isBenignResizeObserverErrorEvent(
        createErrorEvent('Script error.', null)
      )
    ).toBe(false)
  })
})
