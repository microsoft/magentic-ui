import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Markdown } from '@/components/common'

interface ChatInputBannerProps {
  /** Instructional text displayed in the banner. Supports Markdown (e.g. **bold**). */
  message: string
  /** Called when the banner is dismissed */
  onDismiss: () => void
}

/**
 * Inline banner displayed directly above the chat input to provide context
 * or guidance for the next user message — for example after pre-filling a
 * sample task prompt, or after the user releases browser control and needs
 * to describe what they did. Styled to match TakeoverNotice (bg-primary/20).
 */
export function ChatInputBanner({ message, onDismiss }: ChatInputBannerProps) {
  return (
    <div className="bg-primary/20 mb-2 flex w-full items-center gap-3 rounded-lg py-2.5 pr-2.5 pl-4">
      <Markdown className="text-foreground flex-1 text-sm">{message}</Markdown>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 shrink-0"
        onClick={onDismiss}
        aria-label="Dismiss"
      >
        <X className="size-4" />
      </Button>
    </div>
  )
}
