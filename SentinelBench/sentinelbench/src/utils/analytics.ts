import { TaskCompletion } from "../../functions/api/record-completion";
import { TaskView } from "../../functions/api/record-view";

interface RetryOptions {
  maxAttempts: number;
  delayMs: number;
  exponentialBackoff: boolean;
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxAttempts: 3,
  delayMs: 1000,
  exponentialBackoff: true
};

// Generate a random UUID with fallback for environments without crypto.randomUUID
function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  
  // Fallback implementation for environments without crypto.randomUUID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Generate a random user ID if none exists
function getUserId() {
  const storedId = localStorage.getItem("user_id");
  if (storedId) return storedId;

  const newId = generateUUID();
  localStorage.setItem("user_id", newId);
  return newId;
}

// Ensure timestamp is a valid number
function getValidTimestamp(timestamp?: number) {
  if (
    typeof timestamp === "number" &&
    !isNaN(timestamp) &&
    isFinite(timestamp)
  ) {
    return timestamp;
  }
  return Date.now();
}

// Convert timestamp to ISO string and validate date range
function safeDate(timestamp: number): [string, boolean] {
  try {
    const date = new Date(timestamp);
    // Check if date is valid and within reasonable range
    if (
      isNaN(date.getTime()) ||
      date.getFullYear() < 2020 ||
      date.getFullYear() > 2100
    ) {
      return [new Date().toISOString(), false];
    }
    return [date.toISOString(), true];
  } catch {
    return [new Date().toISOString(), false];
  }
}

// Utility function for retrying operations
async function withRetry<T>(
  operation: () => Promise<T>,
  options: RetryOptions = DEFAULT_RETRY_OPTIONS
): Promise<T> {
  let lastError: Error;
  
  for (let attempt = 1; attempt <= options.maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      if (attempt === options.maxAttempts) {
        throw lastError;
      }
      
      const delay = options.exponentialBackoff 
        ? options.delayMs * Math.pow(2, attempt - 1)
        : options.delayMs;
        
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError!;
}

import { TaskStateManager } from './TaskStateManager';

// Store analytics data locally with error handling
function storeAnalyticsData(key: string, data: Record<string, unknown>): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(data));
    return true;
  } catch (error) {
    console.error('Failed to store analytics data:', error);
    
    // If quota exceeded, try to clear old analytics data
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      // Emit storage error through TaskStateManager
      TaskStateManager.emitError({
        type: 'quota_exceeded',
        message: 'Storage quota exceeded while saving analytics. Please clear browser data.',
        taskId: 'analytics'
      });
      
      try {
        const keys = [];
        for (let i = 0; i < localStorage.length; i++) {
          const storageKey = localStorage.key(i);
          if (storageKey && (storageKey.startsWith('completion_') || storageKey.startsWith('view_'))) {
            keys.push(storageKey);
          }
        }
        
        // Remove oldest entries (first 10)
        keys.sort().slice(0, 10).forEach(storageKey => {
          localStorage.removeItem(storageKey);
        });
        
        // Try storing again
        localStorage.setItem(key, JSON.stringify(data));
        return true;
      } catch (cleanupError) {
        console.error('Failed to cleanup and store analytics data:', cleanupError);
        return false;
      }
    }
    
    return false;
  }
}

export async function recordTaskCompletion(
  taskId: string,
  completionTime: number,
  startTime: number
): Promise<boolean> {
  return withRetry(async () => {
    const [validCompletionTime, okCompletionTime] = safeDate(completionTime);
    if (!okCompletionTime) {
      throw new Error("Invalid completion time provided");
    }

    const [validStartTime, okStartTime] = safeDate(startTime);
    if (!okStartTime) {
      throw new Error("Invalid start time provided");
    }

    const completion: TaskCompletion = {
      taskId,
      completionTime: validCompletionTime,
      startTime: validStartTime,
      userId: getUserId(),
      host: window.location.host,
      url: window.location.href,
    };

    // const response = await fetch("/api/record-completion", {
    //   method: "POST",
    //   body: JSON.stringify(completion),
    // });
    // const data = await response.json();
    // return data.success;
    
    // Store locally instead of sending to API
    if (process.env.NODE_ENV === 'development') {
      console.log("Task completion recorded locally:", completion);
    }
    const key = `completion_${taskId}_${Date.now()}`;
    
    if (!storeAnalyticsData(key, completion as unknown as Record<string, unknown>)) {
      throw new Error("Failed to store completion data");
    }
    
    return true;
  }).catch(error => {
    console.error("Failed to record task completion after retries:", error);
    return false;
  });
}

export async function recordTaskView(
  taskId: string,
  viewTime: number
): Promise<boolean> {
  return withRetry(async () => {
    const [viewTimeISO, okViewTime] = safeDate(getValidTimestamp(viewTime));
    if (!okViewTime) {
      throw new Error("Invalid view time provided");
    }

    const view: TaskView = {
      taskId,
      viewTime: viewTimeISO,
      userId: getUserId(),
      host: window.location.host,
      url: window.location.href,
    };

    // const response = await fetch("/api/record-view", {
    //   method: "POST",
    //   body: JSON.stringify(view),
    // });
    // const data = await response.json();
    // return data.success;
    
    // Store locally instead of sending to API
    if (process.env.NODE_ENV === 'development') {
      console.log("Task view recorded locally:", view);
    }
    const key = `view_${taskId}_${Date.now()}`;
    
    if (!storeAnalyticsData(key, view as unknown as Record<string, unknown>)) {
      throw new Error("Failed to store view data");
    }
    
    return true;
  }).catch(error => {
    console.error("Failed to record task view after retries:", error);
    return false;
  });
}
