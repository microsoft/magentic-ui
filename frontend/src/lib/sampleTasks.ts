import { FilePen, Files, FolderTree, LineChart, ShoppingCart, Utensils } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface SampleTask {
  id: string
  /** Short text displayed on the card */
  label: string
  /** Full prompt filled into chat input */
  prompt: string
  /** Lucide icon for the card */
  icon: LucideIcon
  /** Inline banner text shown above the input after selecting this task */
  ctaText: string
  /** Sample files to auto-attach (served from public/sample-task-files/) */
  files?: Array<{ name: string; publicPath: string }>
  /** Whether this task needs a mounted folder */
  needsFolder?: boolean
}

const FOLDER_CTA =
  'Use **Work in Folder** button to select a folder, then click **Send** button to start the task.'
const DEFAULT_CTA =
  'Review the sample prompt and edit if needed. Click **Send** button to start the task.'

export const SAMPLE_TASKS: SampleTask[] = [
  {
    id: 'dedupe-files',
    label: 'Remove duplicate files from a folder',
    prompt:
      'Delete duplicate files in this folder.\nA duplicate is a file whose name is similar AND has the same size. Keep the original file. Only delete the copy.',
    icon: Files,
    ctaText: FOLDER_CTA,
    needsFolder: true,
  },
  {
    id: 'rename-vague-files',
    label: 'Rename files with vague names',
    prompt:
      'Rename files with vague/cryptic FILENAMES based on their content. Skip images and programs.\nA filename is vague if you can\'t guess the topic from it alone (e.g., "jfejfejef.md", "inv_cl_20260501.pdf"). A filename is descriptive if it states the topic (e.g., "packing_list.txt"). Skip descriptive names.\nOne file at a time: use the open tool to read the file, propose new name, then rename. Repeat for the next file.\nAfter each rename, re-list the directory. Walk through every file alphabetically. For each file, either rename it or note "skipped (descriptive/image/program)." Never revisit a file you already renamed or skipped. Stop when you reach the end of the alphabetical list.',
    icon: FilePen,
    ctaText: FOLDER_CTA,
    needsFolder: true,
  },
  {
    id: 'organize-folder',
    label: 'Organize a messy folder',
    prompt:
      'Organize files in this folder into meaningful sub-directories by topic or purpose (e.g. medical, travel, work, finance). Use existing sub-directories when they fit; create new ones only when needed.',
    icon: FolderTree,
    ctaText: FOLDER_CTA,
    needsFolder: true,
  },
  {
    id: 'restaurant-booking',
    label: 'Book a restaurant that matches all your criteria',
    prompt:
      "Book me a table for 4 on resy.com at a well-rated Italian restaurant in the West Village, NYC for Sunday around 7:30 PM. I need real gluten-free options — check the restaurant's actual dinner menu on their website, not just the Resy listing. Use Resy's neighborhood filter to narrow results.",
    icon: Utensils,
    ctaText: DEFAULT_CTA,
  },
  {
    id: 'recipe-shopping',
    label: 'Buy ingredients for a recipe',
    prompt:
      'Find a popular seafood linguini recipe that serves 4 people. Then add all the required ingredients to my Amazon cart. Prioritize Amazon Fresh items for perishables. Do not substitute key ingredients without my approval.',
    icon: ShoppingCart,
    ctaText: DEFAULT_CTA,
  },
  {
    id: 'github-trending',
    label: 'Find and analyze data on the web',
    prompt:
      "Visit GitHub's trending page and pull data for both the 'today' and 'this week' filters. Collect repo name, language, and stars from each view. Create a chart showing which repos appear in both windows vs. only one, with their star counts compared.",
    icon: LineChart,
    ctaText: DEFAULT_CTA,
  },
]

// =============================================================================
// Pending sample task — module-level storage for cross-page navigation
// =============================================================================

/**
 * Stores the sample task selected from SampleTasksPage.
 * ChatView reads and clears this on mount to show banner + attach files.
 * Survives SPA navigation but not full page refresh (which is fine).
 */
let pendingSampleTask: SampleTask | null = null

export function setPendingSampleTask(task: SampleTask | null) {
  pendingSampleTask = task
}

export function consumePendingSampleTask(): SampleTask | null {
  const task = pendingSampleTask
  pendingSampleTask = null
  return task
}
