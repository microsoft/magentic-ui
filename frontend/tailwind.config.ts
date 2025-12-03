import type { Config } from 'tailwindcss'

/**
 * Tailwind CSS v4 Configuration (CSS-First)
 *
 * Colors and design tokens are defined in src/index.css using @theme directive.
 * This config only contains settings that can't be expressed in CSS.
 */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
} satisfies Config
