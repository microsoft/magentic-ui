/**
 * Utility for generating parameter-based passwords for benchmarking
 * Appends URL parameter value to base password: BASEPASSWORD_PARAMETER
 */

import { getTaskPassword, type TaskId } from '../config/passwords';

/**
 * Generate a password using the task's base password and a parameter value
 * Format: BASEPASSWORD_PARAMETER
 * 
 * @param taskId - The task identifier (e.g., 'animal-mover-easy')
 * @param parameterValue - The URL parameter value (e.g., count=4, duration=60)
 * @returns The formatted password (e.g., 'BAAHJUMP_4', 'KABOOM_60')
 */
export const generateParameterPassword = (taskId: TaskId, parameterValue: number | string): string => {
  const basePassword = getTaskPassword(taskId);
  return `${basePassword}_${parameterValue}`;
};
