import { FolderClosed } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export interface FolderChipProps {
  /** Folder name to display */
  name: string
  /** Full folder path shown on hover */
  path: string
}

export function FolderChip({ name, path }: FolderChipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="group/chip border-border-5 flex h-8 cursor-default items-center gap-1.5 overflow-hidden rounded-lg border pr-1.5 text-left"
          aria-label={`${name}: ${path}`}
        >
          <div className="flex h-full w-[26px] shrink-0 items-center justify-center">
            <FolderClosed className="text-muted-foreground size-4" />
          </div>
          <span className="text-foreground truncate text-sm leading-5 font-medium">{name}</span>
        </button>
      </TooltipTrigger>
      <TooltipContent>
        <span>{path}</span>
      </TooltipContent>
    </Tooltip>
  )
}
