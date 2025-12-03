/**
 * Unit tests for file utilities
 *
 * Tests cover:
 * - getFileType: extension → FileType mapping
 * - getFileExtension: filename → extension extraction
 * - isPreviewable: file previewability check
 * - isFileSizeValid: size validation
 * - getFileDownloadUrl: URL construction (PR 283 + legacy)
 * - parseFileInfoFromMetadata: JSON string → FileInfo[] parsing
 * - createFileAttachment: File → FileAttachment conversion
 */

import { describe, it, expect } from 'vitest'
import {
  getFileType,
  getFileExtension,
  isPreviewable,
  isFileSizeValid,
  getFileDownloadUrl,
  parseFileInfoFromMetadata,
  createFileAttachment,
  isMarkdownFile,
  isCodeFile,
  isImageFile,
  getFileIcon,
} from '@/lib/fileUtils'
import { MAX_FILE_UPLOAD_SIZE } from '@/lib/constants'
import {
  File as FileIcon,
  FileText,
  FileCode,
  FileImage,
  FileSpreadsheet,
  FileVideo,
  FileAudio,
  FileArchive,
} from 'lucide-react'

// =============================================================================
// getFileType
// =============================================================================

describe('getFileType', () => {
  it('detects image types', () => {
    expect(getFileType('png')).toBe('image')
    expect(getFileType('jpg')).toBe('image')
    expect(getFileType('svg')).toBe('image')
    expect(getFileType('webp')).toBe('image')
  })

  it('detects code types', () => {
    expect(getFileType('py')).toBe('code')
    expect(getFileType('js')).toBe('code')
    expect(getFileType('ts')).toBe('code')
    expect(getFileType('json')).toBe('code')
    expect(getFileType('html')).toBe('code')
  })

  it('detects text types (including markdown)', () => {
    expect(getFileType('txt')).toBe('text')
    expect(getFileType('csv')).toBe('text')
    expect(getFileType('md')).toBe('text')
    expect(getFileType('markdown')).toBe('text')
  })

  it('detects PDF', () => {
    expect(getFileType('pdf')).toBe('pdf')
  })

  it('returns unknown for unrecognized extensions', () => {
    expect(getFileType('xyz')).toBe('unknown')
    expect(getFileType('docx')).toBe('unknown')
    expect(getFileType('')).toBe('unknown')
  })

  it('is case-insensitive', () => {
    expect(getFileType('PNG')).toBe('image')
    expect(getFileType('Py')).toBe('code')
  })
})

// =============================================================================
// getFileExtension
// =============================================================================

describe('getFileExtension', () => {
  it('extracts extension from filename', () => {
    expect(getFileExtension('report.md')).toBe('md')
    expect(getFileExtension('data.csv')).toBe('csv')
    expect(getFileExtension('script.py')).toBe('py')
  })

  it('handles multiple dots', () => {
    expect(getFileExtension('my.file.name.txt')).toBe('txt')
  })

  it('returns empty string for no extension', () => {
    expect(getFileExtension('Makefile')).toBe('')
    expect(getFileExtension('')).toBe('')
  })

  it('returns lowercase', () => {
    expect(getFileExtension('IMAGE.PNG')).toBe('png')
  })
})

// =============================================================================
// isPreviewable
// =============================================================================

describe('isPreviewable', () => {
  it('returns true for previewable files', () => {
    expect(isPreviewable('report.md')).toBe(true)
    expect(isPreviewable('script.py')).toBe(true)
    expect(isPreviewable('photo.png')).toBe(true)
    expect(isPreviewable('doc.pdf')).toBe(true)
    expect(isPreviewable('data.csv')).toBe(true)
    expect(isPreviewable('config.json')).toBe(true)
  })

  it('returns false for non-previewable files', () => {
    expect(isPreviewable('archive.zip')).toBe(false)
    expect(isPreviewable('document.docx')).toBe(false)
    expect(isPreviewable('binary.exe')).toBe(false)
    expect(isPreviewable('Makefile')).toBe(false)
  })
})

// =============================================================================
// isMarkdownFile / isCodeFile / isImageFile
// =============================================================================

describe('file type helpers', () => {
  it('isMarkdownFile', () => {
    expect(isMarkdownFile('md')).toBe(true)
    expect(isMarkdownFile('markdown')).toBe(true)
    expect(isMarkdownFile('txt')).toBe(false)
  })

  it('isCodeFile', () => {
    expect(isCodeFile('py')).toBe(true)
    expect(isCodeFile('json')).toBe(true)
    expect(isCodeFile('txt')).toBe(false)
  })

  it('isImageFile', () => {
    expect(isImageFile('png')).toBe(true)
    expect(isImageFile('svg')).toBe(true)
    expect(isImageFile('pdf')).toBe(false)
  })
})

// =============================================================================
// isFileSizeValid
// =============================================================================

describe('isFileSizeValid', () => {
  it('accepts files within limit', () => {
    const file = new File(['x'], 'small.txt', { type: 'text/plain' })
    expect(isFileSizeValid(file)).toBe(true)
  })

  it('accepts files exactly at limit', () => {
    const file = new File([new ArrayBuffer(MAX_FILE_UPLOAD_SIZE)], 'exact.bin')
    expect(isFileSizeValid(file)).toBe(true)
  })

  it('rejects files over limit', () => {
    // Create a file larger than limit using Object.defineProperty
    const file = new File(['x'], 'big.bin')
    Object.defineProperty(file, 'size', { value: MAX_FILE_UPLOAD_SIZE + 1 })
    expect(isFileSizeValid(file)).toBe(false)
  })
})

// =============================================================================
// getFileDownloadUrl
// =============================================================================

describe('getFileDownloadUrl', () => {
  it('uses url field (PR 283 format)', () => {
    const file = {
      name: 'report.md',
      url: '/files/user/uid/sid/rid/report.md',
      timestamp: 123,
      extension: 'md',
      file_type: 'text',
      action: 'created' as const,
    }
    expect(getFileDownloadUrl(file)).toBe('/files/user/uid/sid/rid/report.md?v=123')
  })

  it('falls back to path when url is empty', () => {
    const file = {
      name: 'report.md',
      url: '',
      timestamp: 123,
      extension: 'md',
      file_type: 'text',
      action: 'created' as const,
      path: 'files/user/uid/sid/rid/report.md',
    }
    expect(getFileDownloadUrl(file)).toBe('/files/user/uid/sid/rid/report.md?v=123')
  })

  it('returns empty string when no url or path', () => {
    const file = {
      name: 'report.md',
      url: '',
      timestamp: 123,
      extension: 'md',
      file_type: 'text',
      action: 'created' as const,
    }
    expect(getFileDownloadUrl(file)).toBe('')
  })

  it('extracts /files/user/... from absolute disk path', () => {
    const file = {
      name: 'CLAUDE.md',
      url: '',
      timestamp: 123,
      extension: 'md',
      file_type: 'text',
      action: 'created' as const,
      path: '/Users/weilishi/.magentic_ui/files/user/guest/1/1/CLAUDE.md',
    }
    expect(getFileDownloadUrl(file)).toBe('/files/user/guest/1/1/CLAUDE.md?v=123')
  })
})

// =============================================================================
// parseFileInfoFromMetadata
// =============================================================================

describe('parseFileInfoFromMetadata', () => {
  it('parses valid JSON with PR 283 format', () => {
    const json = JSON.stringify([
      {
        name: 'report.csv',
        url: '/files/user/uid/sid/rid/report.csv',
        timestamp: 1709561234.567,
        extension: 'csv',
        file_type: 'csv',
        action: 'created',
      },
    ])
    const result = parseFileInfoFromMetadata(json)
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('report.csv')
    expect(result[0].url).toBe('/files/user/uid/sid/rid/report.csv')
    expect(result[0].action).toBe('created')
    expect(result[0].timestamp).toBe(1709561234.567)
  })

  it('parses legacy format (path only, no url)', () => {
    const json = JSON.stringify([
      {
        name: 'file.py',
        path: 'files/user/uid/sid/rid/file.py',
        extension: 'py',
        type: 'code',
      },
    ])
    const result = parseFileInfoFromMetadata(json)
    expect(result).toHaveLength(1)
    expect(result[0].url).toBe('/files/user/uid/sid/rid/file.py')
    expect(result[0].action).toBe('created') // default
  })

  it('preserves uploadStatus if present', () => {
    const json = JSON.stringify([
      {
        name: 'file.txt',
        url: '/files/test.txt',
        uploadStatus: 'uploading',
      },
    ])
    const result = parseFileInfoFromMetadata(json)
    expect(result[0].uploadStatus).toBe('uploading')
  })

  it('returns empty array for invalid JSON', () => {
    expect(parseFileInfoFromMetadata('not json')).toEqual([])
    expect(parseFileInfoFromMetadata('{}')).toEqual([])
    expect(parseFileInfoFromMetadata('')).toEqual([])
  })

  it('handles multiple files', () => {
    const json = JSON.stringify([
      { name: 'a.txt', url: '/a.txt' },
      { name: 'b.py', url: '/b.py' },
    ])
    const result = parseFileInfoFromMetadata(json)
    expect(result).toHaveLength(2)
  })
})

// =============================================================================
// getFileIcon
// =============================================================================

describe('getFileIcon', () => {
  it('returns FileImage for image extensions', () => {
    expect(getFileIcon('png')).toBe(FileImage)
    expect(getFileIcon('jpg')).toBe(FileImage)
    expect(getFileIcon('SVG')).toBe(FileImage) // case-insensitive
  })

  it('returns FileCode for code extensions', () => {
    expect(getFileIcon('ts')).toBe(FileCode)
    expect(getFileIcon('py')).toBe(FileCode)
    expect(getFileIcon('json')).toBe(FileCode)
  })

  it('returns FileText for markdown and plain text', () => {
    expect(getFileIcon('md')).toBe(FileText)
    expect(getFileIcon('markdown')).toBe(FileText)
    expect(getFileIcon('txt')).toBe(FileText)
    expect(getFileIcon('log')).toBe(FileText)
  })

  it('returns FileSpreadsheet for csv/xlsx (overriding the text bucket)', () => {
    expect(getFileIcon('csv')).toBe(FileSpreadsheet)
    expect(getFileIcon('xlsx')).toBe(FileSpreadsheet)
    expect(getFileIcon('xls')).toBe(FileSpreadsheet)
  })

  it('returns FileText for pdf', () => {
    expect(getFileIcon('pdf')).toBe(FileText)
  })

  it('returns FileVideo / FileAudio / FileArchive for media and archives', () => {
    expect(getFileIcon('mp4')).toBe(FileVideo)
    expect(getFileIcon('mp3')).toBe(FileAudio)
    expect(getFileIcon('zip')).toBe(FileArchive)
  })

  it('falls back to generic File for unknown or empty extensions', () => {
    expect(getFileIcon('xyz')).toBe(FileIcon)
    expect(getFileIcon('')).toBe(FileIcon)
  })
})

// =============================================================================
// createFileAttachment
// =============================================================================

describe('createFileAttachment', () => {
  it('creates attachment from File object', () => {
    const file = new File(['hello'], 'test.txt', { type: 'text/plain' })
    const attachment = createFileAttachment(file)

    expect(attachment.name).toBe('test.txt')
    expect(attachment.mimeType).toBe('text/plain')
    expect(attachment.status).toBe('pending')
    expect(attachment.file).toBe(file)
    expect(attachment.id).toMatch(/^file-/)
  })

  it('generates unique IDs', () => {
    const file1 = new File(['a'], 'a.txt')
    const file2 = new File(['b'], 'b.txt')
    const a1 = createFileAttachment(file1)
    const a2 = createFileAttachment(file2)
    expect(a1.id).not.toBe(a2.id)
  })

  it('defaults mimeType for files without type', () => {
    const file = new File(['x'], 'unknown')
    const attachment = createFileAttachment(file)
    expect(attachment.mimeType).toBe('application/octet-stream')
  })
})
