/**
 * Centralized password configuration for all SentinelBench tasks
 * Passwords are stored here to prevent agents from discovering them in component source code
 */

export const TASK_PASSWORDS = {
  // Reactor tasks
  'reactor-easy': 'IMNOTCLEANINGTHAT',
  'reactor-medium': 'ISTHATAMICROWAVE',
  'reactor-hard': 'WASNOTDISABLED',
  
  // Animal Mover tasks
  'animal-mover-easy': 'BAAHJUMP',
  'animal-mover-medium': 'BAAHDWOLVES',
  'animal-mover-hard': 'THREEPENS',
  
  // Button Presser tasks
  'button-presser-easy': 'ATINYLITTLEBUTTON',
  'button-presser-medium': 'DESTROYTHATBUTTON',
  'button-presser-hard': 'STOPMOVINGAROUND',
  
  // LinkedIn Monitor tasks
  'linkedin-monitor-easy': 'LINKEDINFIND',
  'linkedin-monitor-medium': 'STOPWITHTHESPAM',
  'linkedin-monitor-hard': 'LETMECLICKONTHAT',
  
  // Flight Monitor tasks
  'flight-monitor-easy': 'READYTOFLY',
  'flight-monitor-medium': 'PRETTYCALENDAR',
  'flight-monitor-hard': 'UGHSOMANYADS',
  
  // GitHub Watcher tasks
  'github-watcher-easy': 'WHATAGREATREPO',
  'github-watcher-medium': 'STARGAZER',
  'github-watcher-hard': 'TOOMANYFOLDERS',
  
  // Teams Monitor tasks
  'teams-monitor-easy': 'WELLTHATISBAD',
  'teams-monitor-medium': 'DATABASEGONE',
  'teams-monitor-hard': 'THATWASNTME',
  
  // News Checker tasks
  'news-checker-easy': 'IFONLYICOULDREAD',
  'news-checker-medium': 'ILIKETHISNEWSPAPER',
  'news-checker-hard': 'WHEREAREMYGLASSES',

  // Trading tasks
  'trading-easy': 'BUYTHATHIGH',
  'trading-medium': 'SELLTHATLOW',
  'trading-hard': 'ILIKETHESTOCK',

  // Scholar Watcher tasks
  'scholar-watcher-medium': 'CITATIONNEEDED',
} as const;

export type TaskId = keyof typeof TASK_PASSWORDS;

/**
 * Get the base password for a given task ID
 */
export const getTaskPassword = (taskId: TaskId): string => {
  const password = TASK_PASSWORDS[taskId];
  if (!password) {
    throw new Error(`No password configured for task: ${taskId}`);
  }
  return password;
};

/**
 * Get all available task IDs
 */
export const getTaskIds = (): TaskId[] => {
  return Object.keys(TASK_PASSWORDS) as TaskId[];
};