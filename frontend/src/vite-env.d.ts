/// <reference types="vite/client" />

// Compile-time constant injected by Vite from src/magentic_ui/version.py
declare const __APP_VERSION__: string

// Font packages without TypeScript declarations
declare module '@fontsource-variable/inter'

// YAML files imported as raw strings via Vite's ?raw suffix
declare module '*.yaml?raw' {
  const content: string
  export default content
}

// File System Access API (Chromium-only)
// https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker
interface Window {
  showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>
}
