import { vi } from "vitest"

/** Pretend the browser is `width` px wide (jsdom has no layout). Call `restore()` in a finally/afterEach. */
export const setViewportWidth = (width: number) => {
  const original = window.innerWidth
  const originalMatchMedia = Object.getOwnPropertyDescriptor(window, "matchMedia")
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width })
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  return () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: original })
    if (originalMatchMedia) {
      Object.defineProperty(window, "matchMedia", originalMatchMedia)
    } else {
      Reflect.deleteProperty(window, "matchMedia")
    }
  }
}
