import '@testing-library/jest-dom'

// Mock window.matchMedia for jsdom — required because uiStore calls
// matchMedia('(prefers-color-scheme: dark)') at module init time, and any
// test that imports chatStore (which imports uiStore) would crash without it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: query === '(prefers-color-scheme: dark)',
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})
