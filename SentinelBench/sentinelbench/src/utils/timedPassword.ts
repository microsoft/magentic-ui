/**
 * Utility for generating time-embedded passwords for benchmarking latency
 * Appends elapsed seconds to base password: BASEPASSWORD_TIME123
 */

export const generateTimedPassword = (basePassword: string, elapsedSeconds: number): string => {
  return `${basePassword}_TIME${elapsedSeconds}`;
};

export const calculateElapsedSeconds = (startTime: number): number => {
  return Math.floor((Date.now() - startTime) / 1000);
};