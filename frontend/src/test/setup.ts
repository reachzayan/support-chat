import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, beforeEach, vi } from "vitest"

// jsdom has no media engine. Audio-specific tests supply their own device fake.
beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValue(
    new DOMException("Audio playback is unavailable in jsdom", "NotAllowedError"),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
