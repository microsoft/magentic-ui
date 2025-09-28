/**
 * TaskStateManager - Utility for persisting task state across page refreshes
 */

export interface TaskState {
  timestamp: number;
  [key: string]: unknown;
}

export interface StorageError {
  type: 'quota_exceeded' | 'unavailable' | 'corrupted' | 'unknown';
  message: string;
  taskId: string;
}

export type ErrorCallback = (error: StorageError) => void;

export class TaskStateManager {
  private static readonly PREFIX = 'sentinel_task_';
  private static saveTimeouts: Map<string, number> = new Map();
  private static errorCallbacks: Set<ErrorCallback> = new Set();
  private static isStorageAvailable: boolean | null = null;

  /**
   * Register error callback for handling storage errors
   */
  static onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.add(callback);
    return () => this.errorCallbacks.delete(callback);
  }

  /**
   * Check if localStorage is available
   */
  private static checkStorageAvailability(): boolean {
    if (this.isStorageAvailable !== null) {
      return this.isStorageAvailable;
    }

    try {
      const testKey = '__storage_test__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);
      this.isStorageAvailable = true;
      return true;
    } catch {
      this.isStorageAvailable = false;
      return false;
    }
  }

  /**
   * Emit error to all registered callbacks (public method for external use)
   */
  static emitError(error: StorageError): void {
    // Add a small delay to ensure toast components are mounted
    setTimeout(() => {
      this.errorCallbacks.forEach(callback => {
        try {
          callback(error);
        } catch (e) {
          console.error('Error in storage error callback:', e);
        }
      });
    }, 100);
  }

  /**
   * Save state for a specific task (debounced)
   */
  static saveState(taskId: string, state: Record<string, unknown>): boolean {
    if (!this.checkStorageAvailability()) {
      this.emitError({
        type: 'unavailable',
        message: 'Local storage is not available. Progress cannot be saved.',
        taskId
      });
      return false;
    }

    // Clear any existing timeout for this task
    const existingTimeout = this.saveTimeouts.get(taskId);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
    }
    
    // Set up debounced save (500ms delay)
    const timeoutId = window.setTimeout(() => {
      this.performSave(taskId, state);
      this.saveTimeouts.delete(taskId);
    }, 500);
    
    this.saveTimeouts.set(taskId, timeoutId);
    return true;
  }

  /**
   * Perform immediate save (internal method)
   */
  private static performSave(taskId: string, state: Record<string, unknown>): boolean {
    try {
      const stateWithTimestamp: TaskState = {
        ...state,
        timestamp: Date.now()
      };
      
      // Validate state size (100KB limit)
      const serialized = JSON.stringify(stateWithTimestamp);
      const sizeInBytes = new Blob([serialized]).size;
      const maxSizeInBytes = 100 * 1024; // 100KB
      
      if (sizeInBytes > maxSizeInBytes) {
        this.emitError({
          type: 'unknown',
          message: `State too large (${Math.round(sizeInBytes / 1024)}KB exceeds ${Math.round(maxSizeInBytes / 1024)}KB limit). Some progress may not be saved.`,
          taskId
        });
        return false;
      }
      
      const key = this.getStorageKey(taskId);
      localStorage.setItem(key, serialized);
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'QuotaExceededError') {
        this.emitError({
          type: 'quota_exceeded',
          message: 'Storage quota exceeded. Please clear your browser data or contact support.',
          taskId
        });
      } else {
        this.emitError({
          type: 'unknown',
          message: `Failed to save progress: ${error instanceof Error ? error.message : 'Unknown error'}`,
          taskId
        });
      }
      return false;
    }
  }

  /**
   * Save state immediately (bypass debouncing)
   */
  static saveStateImmediate(taskId: string, state: Record<string, unknown>): boolean {
    if (!this.checkStorageAvailability()) {
      this.emitError({
        type: 'unavailable',
        message: 'Local storage is not available. Progress cannot be saved.',
        taskId
      });
      return false;
    }

    // Clear any pending debounced save
    const existingTimeout = this.saveTimeouts.get(taskId);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
      this.saveTimeouts.delete(taskId);
    }
    
    return this.performSave(taskId, state);
  }

  /**
   * Load state for a specific task
   */
  static loadState(taskId: string): TaskState | null {
    if (!this.checkStorageAvailability()) {
      this.emitError({
        type: 'unavailable',
        message: 'Local storage is not available. Previous progress cannot be restored.',
        taskId
      });
      return null;
    }

    try {
      const key = this.getStorageKey(taskId);
      const saved = localStorage.getItem(key);
      
      if (!saved) {
        return null;
      }
      
      const parsed = JSON.parse(saved);
      
      // Validate that it has a timestamp
      if (!parsed.timestamp) {
        this.emitError({
          type: 'corrupted',
          message: 'Saved progress data is corrupted and has been cleared.',
          taskId
        });
        this.clearState(taskId);
        return null;
      }
      
      return parsed;
    } catch (error) {
      this.emitError({
        type: 'corrupted',
        message: `Failed to restore previous progress: ${error instanceof Error ? error.message : 'Data corruption detected'}`,
        taskId
      });
      this.clearState(taskId);
      return null;
    }
  }

  /**
   * Clear state for a specific task
   */
  static clearState(taskId: string): boolean {
    if (!this.checkStorageAvailability()) {
      return true;
    }

    try {
      const key = this.getStorageKey(taskId);
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      this.emitError({
        type: 'unknown',
        message: `Failed to clear saved progress: ${error instanceof Error ? error.message : 'Unknown error'}`,
        taskId
      });
      return false;
    }
  }

  /**
   * Check if task has saved state
   */
  static hasState(taskId: string): boolean {
    const key = this.getStorageKey(taskId);
    return localStorage.getItem(key) !== null;
  }

  /**
   * Get the elapsed time since the task was first started (from saved state)
   */
  static getElapsedTime(taskId: string): number {
    const state = this.loadState(taskId);
    if (!state || !state.startTime) {
      return 0;
    }
    
    return Date.now() - (state.startTime as number);
  }

  /**
   * Reset task progress (useful for development/testing)
   */
  static resetTask(taskId: string): void {
    this.clearState(taskId);
  }

  /**
   * List all saved task states (useful for debugging)
   */
  static listSavedTasks(): string[] {
    const tasks: string[] = [];
    
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(this.PREFIX)) {
          const taskId = key.replace(this.PREFIX, '');
          tasks.push(taskId);
        }
      }
    } catch (error) {
      console.error('Error listing saved tasks:', error);
    }
    
    return tasks;
  }

  private static getStorageKey(taskId: string): string {
    return `${this.PREFIX}${taskId}`;
  }
}

// Global utility functions for convenience
export const saveTaskState = TaskStateManager.saveState.bind(TaskStateManager);
export const saveTaskStateImmediate = TaskStateManager.saveStateImmediate.bind(TaskStateManager);
export const loadTaskState = TaskStateManager.loadState.bind(TaskStateManager);
export const clearTaskState = TaskStateManager.clearState.bind(TaskStateManager);
export const hasTaskState = TaskStateManager.hasState.bind(TaskStateManager);
export const getTaskElapsedTime = TaskStateManager.getElapsedTime.bind(TaskStateManager);
export const resetTask = TaskStateManager.resetTask.bind(TaskStateManager);