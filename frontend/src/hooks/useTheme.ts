/**
 * Detects the current theme (light/dark) by observing the 'dark' class on document.documentElement.
 * @returns 'dark' | 'light'
 */
import { useState, useEffect } from 'react'

export type Theme = 'dark' | 'light'

export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document !== 'undefined') {
      return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
    }
    return 'dark' // Default to dark
  })

  useEffect(() => {
    const root = document.documentElement

    // Create observer to watch for class changes
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          setTheme(root.classList.contains('dark') ? 'dark' : 'light')
        }
      })
    })

    observer.observe(root, { attributes: true })

    return () => observer.disconnect()
  }, [])

  return theme
}
