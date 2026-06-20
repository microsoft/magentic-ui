import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ChatInput } from '@/components/chat/ChatInput'

vi.mock('@/components/chat/FolderMountDialog', () => ({
  FolderMountDialog: () => null,
}))

vi.mock('@/components/chat/FolderBrowserDialog', () => ({
  FolderBrowserDialog: () => null,
}))

vi.mock('@/components/common', () => ({
  FileChip: () => null,
}))

vi.mock('@/hooks/useFileAttachments', () => ({
  useFileAttachments: () => ({
    attachments: [],
    clearAttachments: vi.fn(),
    removeAttachment: vi.fn(),
    isDragOver: false,
    fileInputRef: { current: null },
    handleFileInputChange: vi.fn(),
    handlePaste: vi.fn(),
    handleDragOver: vi.fn(),
    handleDragLeave: vi.fn(),
    handleDrop: vi.fn(),
  }),
}))

vi.mock('@/hooks/useFolderMount', () => ({
  useFolderMount: () => ({
    mountedFolder: null,
    folderDialogOpen: false,
    setFolderDialogOpen: vi.fn(),
    pendingFolderName: '',
    folderBrowserOpen: false,
    setFolderBrowserOpen: vi.fn(),
    handleSelectFolder: vi.fn(),
    handleBrowserSelect: vi.fn(),
    handleFolderAllow: vi.fn(),
    handleFolderAlwaysAllow: vi.fn(),
    handleFolderCancel: vi.fn(),
    handleDeselectFolder: vi.fn(),
  }),
}))

describe('ChatInput', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('does not submit when Enter is pressed during IME composition', () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        disconnect() {}
      }
    )
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: '你好' } })

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', isComposing: true })
    expect(onSend).not.toHaveBeenCalled()

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', isComposing: false })
    expect(onSend).toHaveBeenCalledWith('你好', undefined)
  })
})
