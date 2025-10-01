/**
 * Application constants to replace magic numbers throughout the codebase
 * Centralized location for commonly used values
 */

// Duration limits (in seconds)
export const DURATION = {
  DEFAULT: 30,
  MIN: 1,
  MAX_HOUR: 3600,           // 1 hour
  MAX_DAY: 86400,           // 24 hours (1 day)
} as const;

// Timeout durations (in milliseconds)
export const TIMEOUT = {
  SHORT: 1000,              // 1 second
  MEDIUM: 2000,             // 2 seconds  
  LONG: 3000,               // 3 seconds
  EXTRA_LONG: 4000,         // 4 seconds
  VERY_LONG: 5000,          // 5 seconds
  SEARCH_BASE: 1000,        // Base search time
  STORAGE_SYNC: 2000,       // Storage sync interval
  TICKER_ANIMATION: 5000,   // News ticker animation
} as const;

// Size limits
export const SIZE = {
  FILE_MAX_KB: 100,         // 100KB file size limit
  POSITION_OFFSET: 30,      // Position offset for elements
  ELEMENT_SIZE: 60,         // Standard element size
  DRAG_Z_INDEX: 1000,       // Z-index for dragging elements
  POPUP_Z_INDEX: 20,        // Z-index for popups
} as const;

// Animation and positioning
export const ANIMATION = {
  MAX_ATTEMPTS: 100,        // Maximum placement attempts
  RANDOM_BASE: 1000,        // Base for random calculations
} as const;

// Common numeric values
export const COMMON = {
  MILLISECONDS_PER_SECOND: 1000,
  VALIDATION_DELAY: 100,    // Validation delay in ms
  DAY_MAX: 31,              // Maximum day in month
  DAY_MIN: 1,               // Minimum day in month
  CALENDAR_YEAR: 2025,      // Current calendar year
  TARGET_DAY: 17,           // Target day for flight booking
  SECONDS_PER_MINUTE: 60,   // Seconds in a minute
  TICKER_START_POS: 100,    // Initial ticker position
  TICKER_RESET_POS: -100,   // Ticker reset position
  GITHUB_STAR_THRESHOLD: 5000,  // GitHub star milestone
  GITHUB_STAR_UPPER: 5100,      // GitHub star upper limit
  MILESTONE_CHECK_INTERVAL: 30, // Check interval for milestones
} as const;